"""
Parse Ravelry API HTML documentation into a structured intermediate dict.
"""

import re
import sys
from bs4 import BeautifulSoup, Tag


def clean_text(text: str) -> str:
    """Strip and collapse whitespace."""
    return re.sub(r"\s+", " ", text or "").strip()


def parse_type_cell(td) -> dict:
    """
    Parse a <td class="type"> cell.
    Returns a dict with:
      - raw: original cleaned text
      - base_type: e.g. "String", "Integer", "Boolean", "Array", "Hash", or None
      - ref_id: anchor id of the linked result object (e.g. "User_full_result"), or None
      - ref_name: human name like "User", or None
      - ref_variant: variant suffix like "full", "list", "POST", or None
      - is_array: True if the cell starts with "Array,"
    """
    if td is None:
        return {"raw": "", "base_type": None, "ref_id": None, "ref_name": None, "ref_variant": None, "is_array": False}

    raw = clean_text(td.get_text())
    result = {
        "raw": raw,
        "base_type": None,
        "ref_id": None,
        "ref_name": None,
        "ref_variant": None,
        "is_array": False,
    }

    if re.search(r"\bArray\b", raw, re.IGNORECASE):
        result["is_array"] = True

    a_tag = td.find("a")
    if a_tag:
        href = a_tag.get("href", "")
        anchor_match = re.search(r"#(.+)$", href)
        if anchor_match:
            result["ref_id"] = anchor_match.group(1)

        link_text = clean_text(a_tag.get_text())
        variant_match = re.search(r"\((.+?)\)", link_text)
        if variant_match:
            result["ref_variant"] = variant_match.group(1).strip()
            result["ref_name"] = re.sub(r"\s*\(.*?\)", "", link_text).strip()
        else:
            result["ref_name"] = link_text if link_text else None

    if not result["ref_name"] or not result["ref_name"].strip():
        result["ref_name"] = None
        result["ref_id"] = None
        for type_kw in ["Integer", "String", "Boolean", "Float", "Hash", "Array"]:
            if re.search(rf"\b{type_kw}\b", raw, re.IGNORECASE):
                result["base_type"] = type_kw
                break
    else:
        for type_kw in ["Integer", "String", "Boolean", "Float", "Hash", "Array"]:
            if re.search(rf"^{type_kw}\b", raw, re.IGNORECASE):
                if type_kw.lower() != result["ref_name"].lower():
                    result["base_type"] = type_kw
                break

    return result


def parse_parameters_table(table) -> list:
    """Parse a .parameters table. Returns list of param dicts."""
    if table is None:
        return []
    rows = []
    for tr in table.find("tbody").find_all("tr") if table.find("tbody") else []:
        tds = tr.find_all("td")
        if len(tds) < 4:
            continue
        name = clean_text(tds[0].get_text())
        type_info = parse_type_cell(tds[1])
        required_text = clean_text(tds[2].get_text()).lower()
        required = "yes" in required_text
        description = clean_text(tds[3].get_text())
        rows.append({
            "name": name,
            "type": type_info,
            "required": required,
            "description": description,
        })
    return rows


def parse_model_attributes_table(table) -> list:
    """Parse a model_attributes .parameters table (Name/Type/Nullable/Description)."""
    if table is None:
        return []
    rows = []
    for tr in table.find("tbody").find_all("tr") if table.find("tbody") else []:
        tds = tr.find_all("td")
        if len(tds) < 4:
            continue
        name = clean_text(tds[0].get_text())
        type_info = parse_type_cell(tds[1])
        nullable_text = clean_text(tds[2].get_text()).lower()
        nullable = "yes" in nullable_text
        description = clean_text(tds[3].get_text())
        rows.append({
            "name": name,
            "type": type_info,
            "nullable": nullable,
            "description": description,
        })
    return rows


def parse_endpoint(div) -> dict:
    """Parse a single <div class="api_method"> into an endpoint dict."""
    h3 = div.find("h3")
    endpoint_id = h3.get("id", "") if h3 else ""
    small = h3.find("small") if h3 else None
    authenticated = bool(small and "authenticated" in clean_text(small.get_text()).lower())
    if small:
        small.extract()
    endpoint_name = clean_text(h3.get_text()) if h3 else ""

    method_info = div.find("div", class_="method_information")
    if method_info is None:
        return {
            "id": endpoint_id,
            "name": endpoint_name,
            "authenticated": authenticated,
            "http_method": None,
            "path": None,
            "description": "",
            "uri_parameters": [],
            "input_parameters": [],
            "return_values": [],
        }

    uri_div = method_info.find("div", class_="uri")
    http_method, path = None, None
    if uri_div:
        uri_text = clean_text(uri_div.get_text())
        parts = uri_text.split()
        if parts:
            http_method = parts[0].upper()
            path = " ".join(parts[1:]) if len(parts) > 1 else ""
            path = re.sub(r"\.json$", "", path)

    description_div = method_info.find("div", class_="description")
    description = clean_text(description_div.get_text()) if description_div else ""

    uri_params_div = method_info.find("div", class_="uri_parameters")
    uri_params_table = uri_params_div.find("table", class_="parameters") if uri_params_div else None
    uri_parameters = parse_parameters_table(uri_params_table)

    input_params_div = method_info.find("div", class_="input_parameters")
    input_params_table = input_params_div.find("table", class_="parameters") if input_params_div else None
    input_parameters = parse_parameters_table(input_params_table)

    return_div = method_info.find("div", class_="return_values")
    return_table = return_div.find("table", class_="parameters") if return_div else None
    return_values = parse_parameters_table(return_table)

    return {
        "id": endpoint_id,
        "name": endpoint_name,
        "authenticated": authenticated,
        "http_method": http_method,
        "path": path,
        "description": description,
        "uri_parameters": uri_parameters,
        "input_parameters": input_parameters,
        "return_values": return_values,
    }


def parse_api_methods(soup) -> list:
    """
    Walk the DOM to extract resource groups and their endpoints.
    Returns a list of group dicts, each with a list of endpoint dicts.
    """
    methods_div = soup.find("div", id="methods")
    if methods_div is None:
        methods_div = soup.find("div", class_="doc_content")
    if methods_div is None:
        print("ERROR: Could not find div#methods or .doc_content div", file=sys.stderr)
        return []

    groups = []
    current_group = None

    for element in methods_div.children:
        if not isinstance(element, Tag):
            continue

        if element.name == "h2" and "api_group" in element.get("class", []):
            group_name = clean_text(element.get_text())
            current_group = {"group": group_name, "endpoints": []}
            groups.append(current_group)
            continue

        if element.name == "div" and "api_method" in element.get("class", []):
            if current_group is None:
                current_group = {"group": "(top level)", "endpoints": []}
                groups.append(current_group)
            current_group["endpoints"].append(parse_endpoint(element))

    return groups


def parse_result_objects(soup) -> list:
    """
    Parse the #result_objects section.
    Returns a list of model group dicts, each with a list of variant dicts.
    """
    result_objects_div = soup.find("div", id="result_objects")
    if result_objects_div is None:
        print("WARNING: Could not find #result_objects div", file=sys.stderr)
        return []

    models = []
    current_model_group = None
    current_variant = None

    for element in result_objects_div.children:
        if not isinstance(element, Tag):
            continue

        if element.name == "h2" and "api_model" in element.get("class", []):
            model_name = clean_text(element.get_text())
            model_id = element.get("id", "")
            current_model_group = {
                "id": model_id,
                "name": model_name,
                "variants": [],
            }
            models.append(current_model_group)
            current_variant = None
            continue

        if element.name == "h3":
            if current_model_group is None:
                continue
            variant_id = element.get("id", "")
            variant_text = clean_text(element.get_text())
            variant_qualifier = None
            id_match = re.match(r"^(.+?)_([^_]+)_result$", variant_id)
            if id_match:
                variant_qualifier = id_match.group(2)
                if variant_qualifier == "":
                    variant_qualifier = None
            current_variant = {
                "id": variant_id,
                "text": variant_text,
                "variant": variant_qualifier,
                "fields": [],
            }
            current_model_group["variants"].append(current_variant)
            continue

        if element.name == "div" and "model_attributes" in element.get("class", []):
            if current_variant is None:
                continue
            table = element.find("table", class_="parameters")
            current_variant["fields"] = parse_model_attributes_table(table)
            continue

    return models


def parse(html_content: str) -> dict:
    """
    Parse Ravelry API HTML documentation.
    Returns a dict with 'api_groups' and 'result_objects'.
    """
    soup = BeautifulSoup(html_content, "lxml")

    groups = parse_api_methods(soup)
    total_endpoints = sum(len(g["endpoints"]) for g in groups)
    print(f"  Found {len(groups)} resource groups, {total_endpoints} endpoints")

    result_objects = parse_result_objects(soup)
    total_variants = sum(len(m["variants"]) for m in result_objects)
    print(f"  Found {len(result_objects)} model groups, {total_variants} variants")

    return {
        "api_groups": groups,
        "result_objects": result_objects,
    }
