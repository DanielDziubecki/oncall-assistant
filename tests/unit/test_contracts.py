from oncall.contracts import DEFAULT_DIR, json_schemas, render


def test_committed_schemas_are_up_to_date() -> None:
    generated = json_schemas()

    stale = [
        path
        for path, schema in generated.items()
        if not (DEFAULT_DIR / path).is_file() or (DEFAULT_DIR / path).read_text() != render(schema)
    ]
    assert not stale, f"run `make schemas` and commit the result: {stale}"


def test_no_orphaned_schema_files() -> None:
    committed = {p.relative_to(DEFAULT_DIR).as_posix() for p in DEFAULT_DIR.rglob("*.json")}

    assert committed == set(json_schemas())


def test_schemas_forbid_additional_properties() -> None:
    for path, schema in json_schemas().items():
        objects = [schema, *schema.get("$defs", {}).values()]
        open_objects = [
            obj.get("title")
            for obj in objects
            if obj.get("type") == "object"
            and "properties" in obj
            and obj.get("additionalProperties") is not False
        ]
        assert not open_objects, f"{path}: {open_objects}"
