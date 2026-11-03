"""Exercise schema contracts without claiming to test the SkyGuard backend."""
from pathlib import Path
from copy import deepcopy
from importlib.metadata import version
import json
from validate import make_validator, load_json, errors_for, strict_loads

BASE = Path(__file__).resolve().parent
PAIRS = {
    'status': ('status-update.schema.json', 'status-update.valid.json'),
    'sos': ('sos.schema.json', 'sos.valid.json'),
    'shelter': ('shelter-feature.schema.json', 'shelter-feature.valid.json'),
    'audit': ('audit-entry.schema.json', 'audit-entry.valid.json'),
}
validators = {}; examples = {}; results = []
for key, (schema_file, example_file) in PAIRS.items():
    validators[key] = make_validator(load_json(BASE / 'schemas' / schema_file))
    examples[key] = load_json(BASE / 'examples' / example_file)

def case(name, key, expected_valid, edit=None):
    obj = deepcopy(examples[key])
    if edit: edit(obj)
    errs = errors_for(validators[key], obj)
    actual = not errs
    results.append({'name': name, 'schema': key, 'expected_valid': expected_valid,
                    'actual_valid': actual, 'passed': actual == expected_valid,
                    'error_keywords': sorted({e['keyword'] for e in errs})})

def setv(**kwargs):
    return lambda obj: obj.update(kwargs)

def drop(*keys):
    return lambda obj: [obj.pop(key, None) for key in keys]

for key in PAIRS: case('Valid example: ' + key, key, True)
case('Status minimal optional fields omitted', 'status', True, drop('comment', 'current_occupancy'))
case('Status inclusive coordinate boundaries', 'status', True, setv(user_latitude=90, user_longitude=-180))
case('Status actual occupancy can exceed nominal capacity', 'status', True, setv(status='OVERCROWDED', current_occupancy=120))
case('Status coordinate distance is a backend check', 'status', True, setv(user_latitude=50.0, user_longitude=25.0))
case('Status fractional UTC timestamp', 'status', True, setv(observed_at='2026-11-03T20:00:00.123456Z'))
for name, data in [
    ('latitude outside range', {'user_latitude': 90.01}),
    ('longitude outside range', {'user_longitude': -180.01}),
    ('string coordinate', {'user_latitude': '49.84'}),
    ('negative accuracy', {'location_accuracy_m': -1}),
    ('boolean occupancy', {'current_occupancy': True}),
    ('negative occupancy', {'current_occupancy': -1}),
    ('null optional occupancy', {'current_occupancy': None}),
    ('unknown status', {'status': 'open'}),
    ('blank comment', {'comment': '   '}),
    ('invalid calendar date', {'observed_at': '2026-02-30T20:00:00Z'}),
    ('missing timezone', {'observed_at': '2026-11-03T20:00:00'}),
    ('non-UTC timestamp profile', {'observed_at': '2026-11-03T22:00:00+02:00'}),
    ('invalid UUID', {'requestId': 'not-a-uuid'}),
    ('incorrect version', {'schema_version': '2.0.0'}),
    ('project shelter ID pattern', {'shelter_id': '../shelters/1'}),
    ('spoofed role', {'role': 'Shelter Manager'}),
    ('spoofed author', {'actor_id': '00000000-0000-4000-8000-000000000999'}),
    ('client-computed distance', {'distance_m': 0}),
    ('unknown extra field', {'unexpected': 1}),
]: case('Reject status ' + name, 'status', False, setv(**data))
case('SOS minimal MEDICAL without shelter/contact/message', 'sos', True, drop('shelter_id', 'contact_phone', 'message', 'people_affected'))
case('SOS OTHER with description', 'sos', True, setv(incident_type='OTHER', message='Навчальна інша подія.'))
case('SOS no 100 m shelter restriction', 'sos', True, setv(user_latitude=51.0, user_longitude=26.0))
case('SOS optional contact and known shelter', 'sos', True, setv(contact_phone='+380000000000', shelter_id='SH-LVIV-001'))
case('Reject SOS OTHER without description', 'sos', False, lambda o: (o.update(incident_type='OTHER'), o.pop('message', None)))
for name, data in [
    ('blank OTHER description', {'incident_type': 'OTHER', 'message': '\t '}),
    ('unknown incident type', {'incident_type': 'PANIC'}),
    ('zero affected people', {'people_affected': 0}),
    ('boolean affected people', {'people_affected': False}),
    ('invalid phone', {'contact_phone': 'call me'}),
    ('out-of-range SOS coordinate', {'user_latitude': 91}),
    ('fake server processing status', {'status': 'ACCEPTED'}),
    ('fake assigned operator', {'assigned_operator_id': 'operator-1'}),
    ('empty supplied shelter ID', {'shelter_id': ''}),
]: case('Reject SOS ' + name, 'sos', False, setv(**data))
case('Shelter can be unconfirmed', 'shelter', True, lambda o: o['properties'].update(last_confirmed_at=None))
case('Shelter optional occupancy omitted', 'shelter', True, lambda o: o['properties'].pop('current_occupancy'))
case('Reject confidential field in public Shelter', 'shelter', False, lambda o: o['properties'].update(commander_phone='+380000000000'))
case('Reject reporter GPS in public Shelter', 'shelter', False, lambda o: o['properties'].update(user_latitude=49.84))
case('Reject non-point geometry', 'shelter', False, lambda o: o['geometry'].update(type='Polygon'))
case('Reject third coordinate in this 2D profile', 'shelter', False, lambda o: o['geometry'].update(coordinates=[24.03,49.84,300]))
case('Reject latitude 91 in GeoJSON tuple', 'shelter', False, lambda o: o['geometry'].update(coordinates=[24.03,91]))
case('Reject capacity below project minimum', 'shelter', False, lambda o: o['properties'].update(capacity=9))
case('Reject string resource flag', 'shelter', False, lambda o: o['properties'].update(has_starlink='false'))
case('Audit anonymous event with null identity', 'audit', True, setv(role='Anonymous', actor_id=None))
case('Audit optional measured distance', 'audit', True, setv(distance_m=1200.0))
for name, data in [
    ('unknown role alias', {'role': 'DSNS_OFFICER'}),
    ('Anonymous with identity', {'role': 'Anonymous'}),
    ('Citizen without identity', {'actor_id': None}),
    ('short hash', {'sha256_hash': 'abc'}),
    ('invalid hexadecimal hash', {'previous_hash': 'g'*64}),
    ('negative sequence', {'sequence': -1}),
    ('non-HTTP status', {'status_code': 700}),
    ('exact GPS data forbidden', {'user_latitude': 49.84}),
]: case('Reject audit ' + name, 'audit', False, setv(**data))
# Required fields are exercised individually, not merely by passing an empty object.
for key, validator in validators.items():
    for field in validator.schema['required']:
        case('Reject missing required ' + key + '.' + field, key, False, drop(field))
for name, text in [('NaN token', '{"value":NaN}'), ('duplicate JSON key', '{"x":1,"x":2}')]:
    rejected = False
    try: strict_loads(text)
    except ValueError: rejected = True
    results.append({'name':'Strict parser rejects ' + name, 'schema':'parser', 'expected_valid':False, 'actual_valid':not rejected, 'passed':rejected, 'error_keywords':['parse'] if rejected else []})
summary = {'validator':'jsonschema', 'validator_version':version('jsonschema'),
           'draft':'2020-12', 'format_checker_enabled':True,
           'schemas_meta_validated':len(validators), 'total_cases':len(results),
           'passed':sum(r['passed'] for r in results), 'failed':sum(not r['passed'] for r in results),
           'scope':'JSON parsing and schema validation only; no live backend, RBAC, consent registry, geofence, quorum or cryptographic integrity test.',
           'results':results}
(BASE / 'validation_report.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n', encoding='utf-8')
print(json.dumps({k:v for k,v in summary.items() if k!='results'},ensure_ascii=False,indent=2))
raise SystemExit(1 if summary['failed'] else 0)
