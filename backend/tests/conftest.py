"""测试共享工具：schema 组件解析（兼容 $ref / allOf 包装）。"""


def resolve_node(schema, node):
    """递归解包 $ref / allOf，返回最终 schema dict。"""
    if not isinstance(node, dict):
        return {}
    if "$ref" in node:
        name = node["$ref"].rsplit("/", 1)[-1]
        return resolve_node(schema, schema["components"]["schemas"].get(name, {}))
    if "allOf" in node:
        merged = {k: v for k, v in node.items() if k != "allOf"}
        for sub in node["allOf"]:
            merged.update(resolve_node(schema, sub))
        return merged
    return node


def list_items_component(schema, path: str):
    """列表端点响应 → PageResponse 信封组件 → items 元素组件。"""
    resp = schema["paths"][path]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    if "$ref" in resp:
        resp = resolve_node(schema, resp)
    items = resp["properties"]["items"]
    ref = items["items"]["$ref"] if "items" in items else items["$ref"]
    return resolve_node(schema, {"$ref": ref})
