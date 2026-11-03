"""Validate a UTF-8 JSON file against a self-contained Draft 2020-12 schema."""
import argparse
import json
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker

def reject_constant(value):
    raise ValueError('Non-JSON numeric constant: ' + value)

def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate object key: ' + key)
        result[key] = value
    return result

def strict_loads(text):
    return json.loads(text, parse_constant=reject_constant, object_pairs_hook=unique_object)

def load_json(path):
    return strict_loads(Path(path).read_text(encoding='utf-8'))

def make_validator(schema):
    Draft202012Validator.check_schema(schema)
    checker = FormatChecker()
    if 'date-time' not in checker.checkers or 'uuid' not in checker.checkers:
        raise RuntimeError('Install jsonschema[format]; date-time and uuid checks are required.')
    return Draft202012Validator(schema, format_checker=checker)

def errors_for(validator, instance):
    return [
        {'path': '/' + '/'.join(str(p) for p in error.absolute_path), 'keyword': error.validator, 'message': error.message}
        for error in validator.iter_errors(instance)
    ]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('schema')
    parser.add_argument('instance')
    args = parser.parse_args()
    try:
        validator = make_validator(load_json(args.schema))
        errors = errors_for(validator, load_json(args.instance))
    except (OSError, ValueError) as exc:
        print(json.dumps({'valid': False, 'parse_error': str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps({'valid': not errors, 'errors': errors}, ensure_ascii=False, indent=2))
    return 1 if errors else 0

if __name__ == '__main__':
    raise SystemExit(main())
