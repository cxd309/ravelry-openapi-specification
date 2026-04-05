"""
Generate an OpenAPI 3.1 spec dict from parsed Ravelry API data.
"""

import re

SERVER_URL = "https://api.ravelry.com"

TYPE_MAP = {
    "string": {"type": "string"},
    "integer": {"type": "integer"},
    "boolean": {"type": "boolean"},
    "float": {"type": "number", "format": "float"},
    "number": {"type": "number"},
    "array": {"type": "array", "items": {}},
    "hash": {"type": "object"},
    "object": {"type": "object"},
}

STUB_SCHEMAS: dict[str, dict] = {
    "DateTime":       {"type": "string", "format": "date-time"},
    "DateTimePOST":   {"type": "string", "format": "date-time"},
    "Decimal":        {"type": "number"},
    "DecimalPOST":    {"type": "number"},
    "Array":          {"type": "array", "items": {}},
    "ArrayPOST":      {"type": "array", "items": {}},
    "Object":         {"type": "object"},
    "ObjectPOST":     {"type": "object"},
    "Optional":       {"type": "string", "description": "Optional value"},
    "Brand":                  {"type": "object", "description": "Brand object (undocumented)"},
    "Collection":             {"type": "object", "description": "Collection object (undocumented)"},
    "DownloadLocation":       {"type": "object", "description": "Download location (undocumented)"},
    "FiberCategoryFull":      {"type": "object", "description": "FiberCategory full variant (undocumented)"},
    "FiberPackStash":         {"type": "object", "description": "FiberPack stash variant (undocumented)"},
    "File":                   {"type": "object", "description": "Uploaded file object (undocumented)"},
    "Forum":                  {"type": "object", "description": "Forum object (undocumented)"},
    "ForumMarkers":           {"type": "object", "description": "Forum vote markers (undocumented)"},
    "ForumSet":               {"type": "object", "description": "Forum set object (undocumented)"},
    "LoveknittingProductFull": {"type": "object", "description": "LoveKnitting product (undocumented)"},
    "Multipart":              {"type": "string", "format": "binary", "description": "Multipart file upload"},
    "Paginator":              {
        "type": "object",
        "description": "Pagination metadata",
        "properties": {
            "page":       {"type": "integer"},
            "page_size":  {"type": "integer"},
            "results":    {"type": "integer"},
            "last_page":  {"type": "integer"},
            "page_count": {"type": "integer"},
        }
    },
    "PhotoSize":              {"type": "object", "description": "Photo size (undocumented)"},
    "Product":                {"type": "object", "description": "Product object (undocumented)"},
    "TopicStatus":            {"type": "object", "description": "Topic status (undocumented)"},
    "YarnAttributeFull":      {"type": "object", "description": "YarnAttribute full variant (undocumented)"},
    "YarnAttributePublic":    {"type": "object", "description": "YarnAttribute public variant (undocumented)"},
    "YarnWeightFull":         {"type": "object", "description": "YarnWeight full variant (undocumented)"},
}


def make_schema_name_from_id(result_id: str) -> str:
    """
    Convert a result object id like "User_full_result" into a PascalCase schema name.

    Examples:
      User_full_result                    -> UserFull
      Business__result                    -> Business
      QueuedProject_full_for_owner_result -> QueuedProjectFullForOwner
      Bundle_POST_result                  -> BundlePost
    """
    s = re.sub(r"_result$", "", result_id)
    parts = [p for p in s.split("_") if p]
    if not parts:
        return "Unknown"
    return "".join(p[0].upper() + p[1:] for p in parts)


def make_schema_name(model_name: str, variant: str | None) -> str:
    """Produce a schema name from model + variant consistent with make_schema_name_from_id."""
    name = model_name.strip()
    if not variant or not variant.strip():
        return name
    v_parts = [p[0].upper() + p[1:] for p in variant.strip().split("_") if p]
    return f"{name}{''.join(v_parts)}"


def ravelry_type_to_openapi(type_info: dict) -> dict:
    """Convert a parsed type_info dict into an OpenAPI schema object."""
    is_array = type_info.get("is_array", False)
    ref_name = type_info.get("ref_name")
    ref_variant = type_info.get("ref_variant")
    base_type = (type_info.get("base_type") or "").lower()
    raw = type_info.get("raw", "")

    inner_schema: dict = {}

    if ref_name and ref_name.strip():
        ref_id = type_info.get("ref_id")
        if ref_id:
            schema_name = make_schema_name_from_id(ref_id)
        else:
            schema_name = make_schema_name(ref_name, ref_variant)
        inner_schema = {"$ref": f"#/components/schemas/{schema_name}"}
    elif base_type in TYPE_MAP:
        inner_schema = dict(TYPE_MAP[base_type])
    else:
        raw_lower = raw.lower()
        if "integer" in raw_lower or "int" in raw_lower:
            inner_schema = {"type": "integer"}
        elif "boolean" in raw_lower or "bool" in raw_lower:
            inner_schema = {"type": "boolean"}
        elif "float" in raw_lower or "number" in raw_lower or "decimal" in raw_lower:
            inner_schema = {"type": "number"}
        elif "hash" in raw_lower or "object" in raw_lower:
            inner_schema = {"type": "object"}
        else:
            inner_schema = {"type": "string"}

    if is_array:
        return {"type": "array", "items": inner_schema} if inner_schema else {"type": "array", "items": {}}

    return inner_schema if inner_schema else {"type": "string"}


def sanitize_operation_id(endpoint_id: str) -> str:
    """Convert endpoint id like 'bundles_create' to camelCase."""
    s = endpoint_id.lstrip("/").lstrip("_")
    parts = re.split(r"[/_\-]+", s)
    if not parts:
        return "operation"
    result = parts[0]
    for p in parts[1:]:
        result += p[0].upper() + p[1:] if p else ""
    return result or "operation"


def path_params_from_path(path: str) -> list[str]:
    """Extract {param_name} from a path string."""
    return re.findall(r"\{([^}]+)\}", path)


def build_parameter(param: dict, location: str) -> dict:
    """Build an OpenAPI parameter object."""
    p: dict = {
        "name": param["name"],
        "in": location,
        "required": param["required"] if location == "path" else param.get("required", False),
        "schema": ravelry_type_to_openapi(param["type"]),
    }
    if param.get("description"):
        p["description"] = param["description"]
    return p


def build_request_body(params: list) -> dict:
    """Build an OpenAPI requestBody from input parameters."""
    properties = {}
    required_fields = []
    for param in params:
        schema = ravelry_type_to_openapi(param["type"])
        if param.get("description"):
            schema = dict(schema)
            schema["description"] = param["description"]
        properties[param["name"]] = schema
        if param.get("required"):
            required_fields.append(param["name"])

    schema_obj: dict = {"type": "object", "properties": properties}
    if required_fields:
        schema_obj["required"] = required_fields

    return {
        "required": bool(required_fields),
        "content": {"application/json": {"schema": schema_obj}},
    }


def build_response_schema(return_values: list) -> dict:
    """Build a response schema from return values."""
    if not return_values:
        return {"type": "object"}
    if len(return_values) == 1:
        rv = return_values[0]
        return {"type": "object", "properties": {rv["name"]: ravelry_type_to_openapi(rv["type"])}}
    return {"type": "object", "properties": {rv["name"]: ravelry_type_to_openapi(rv["type"]) for rv in return_values}}


def build_paths(api_groups: list) -> dict:
    """Build the OpenAPI paths object."""
    paths: dict = {}
    operation_id_counts: dict[str, int] = {}

    for group in api_groups:
        tag = group["group"] if group["group"] != "/" else "general"

        for endpoint in group["endpoints"]:
            path = endpoint.get("path")
            if not path:
                continue
            method = (endpoint.get("http_method") or "GET").lower()
            path = re.sub(r"\.json$", "", path)

            if path not in paths:
                paths[path] = {}

            base_op_id = sanitize_operation_id(endpoint["id"])
            if base_op_id in operation_id_counts:
                operation_id_counts[base_op_id] += 1
                op_id = f"{base_op_id}{operation_id_counts[base_op_id]}"
            else:
                operation_id_counts[base_op_id] = 0
                op_id = base_op_id

            operation: dict = {
                "operationId": op_id,
                "tags": [tag],
                "summary": endpoint.get("name") or endpoint.get("id") or "",
            }
            if endpoint.get("description"):
                operation["description"] = endpoint["description"]

            parameters = []
            uri_params = endpoint.get("uri_parameters", [])
            for p in uri_params:
                parameters.append(build_parameter(p, "path"))

            declared_path_params = {p["name"] for p in uri_params}
            for pname in path_params_from_path(path):
                if pname not in declared_path_params:
                    parameters.append({
                        "name": pname,
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    })

            input_params = endpoint.get("input_parameters", [])
            uses_request_body = method in ("post", "put", "patch")

            if uses_request_body:
                if input_params:
                    operation["requestBody"] = build_request_body(input_params)
            else:
                for p in input_params:
                    parameters.append(build_parameter(p, "query"))

            if parameters:
                operation["parameters"] = parameters

            response_schema = build_response_schema(endpoint.get("return_values", []))
            operation["responses"] = {
                "200": {
                    "description": "Success",
                    "content": {"application/json": {"schema": response_schema}},
                }
            }

            if endpoint.get("authenticated"):
                operation["security"] = [{"oauth2": []}, {"basicAuth": []}]
            else:
                operation["security"] = [{"basicAuth": []}]

            paths[path][method] = operation

    return paths


def build_schemas(result_objects: list) -> dict:
    """Build the OpenAPI components/schemas from result objects."""
    schemas: dict = {}

    for model_group in result_objects:
        for variant in model_group["variants"]:
            schema_name = make_schema_name_from_id(variant["id"])
            if not schema_name or schema_name == "Unknown":
                continue

            properties = {}
            for field in variant.get("fields", []):
                if not field["name"]:
                    continue
                schema = ravelry_type_to_openapi(field["type"])
                if field.get("description"):
                    schema = dict(schema)
                    schema["description"] = field["description"]
                properties[field["name"]] = schema

            schema_obj: dict = {"type": "object"}
            if properties:
                schema_obj["properties"] = properties
            schemas[schema_name] = schema_obj

    for stub_name, stub_schema in STUB_SCHEMAS.items():
        if stub_name not in schemas:
            schemas[stub_name] = stub_schema

    return schemas


def generate(api_groups: list, result_objects: list) -> dict:
    """
    Generate a complete OpenAPI 3.1 document from parsed Ravelry API data.
    Returns the spec as a dict.
    """
    paths = build_paths(api_groups)
    total_ops = sum(len(v) for v in paths.values())
    print(f"  {len(paths)} unique paths, {total_ops} total operations")

    schemas = build_schemas(result_objects)
    print(f"  {len(schemas)} schemas")

    auth_count = sum(1 for g in api_groups for ep in g["endpoints"] if ep.get("authenticated"))
    unauth_count = sum(1 for g in api_groups for ep in g["endpoints"] if not ep.get("authenticated"))
    print(f"  {auth_count} authenticated endpoints, {unauth_count} unauthenticated")

    return {
        "openapi": "3.1.0",
        "info": {
            "title": "Ravelry API",
            "description": (
                "Ravelry REST API. Supports HTTP Basic Auth (read-only) and OAuth 2.0 "
                "for authenticated endpoints."
            ),
            "version": "1.0.0",
            "contact": {
                "email": "api@ravelry.com",
                "url": "https://www.ravelry.com/api",
            },
        },
        "servers": [{"url": SERVER_URL, "description": "Ravelry API"}],
        "tags": [
            {"name": group["group"] if group["group"] != "/" else "general"}
            for group in api_groups
        ],
        "paths": paths,
        "components": {
            "schemas": schemas,
            "securitySchemes": {
                "oauth2": {
                    "type": "oauth2",
                    "flows": {
                        "authorizationCode": {
                            "authorizationUrl": "https://www.ravelry.com/oauth2/auth",
                            "tokenUrl": "https://www.ravelry.com/oauth2/token",
                            "scopes": {
                                "offline": "Request refresh tokens",
                                "forum-write": "Create, edit, and delete forum posts",
                                "message-write": "Create and delete private messages",
                                "patternstore-read": "Enumerate pattern stores and products",
                                "patternstore-pdf": "Generate download links for PDFs in pattern stores",
                                "deliveries-read": "List products purchased by or gifted to the current user",
                                "library-pdf": "Directly download PDFs from a user's library",
                                "profile-only": "Access to /current_user.json only",
                                "carts-only": "Access to /carts/*.json only",
                            }
                        }
                    }
                },
                "basicAuth": {
                    "type": "http",
                    "scheme": "basic",
                    "description": (
                        "HTTP Basic Auth. Use read-only credentials for unauthenticated endpoints, "
                        "or personal access key + personal key for full account access."
                    ),
                }
            }
        }
    }
