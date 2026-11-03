"""T3 OpenAPI 文档与 schema 全局约定。

全局约束：每个端点必须有类型化 schema——Choice 枚举进 enum、金额 int64、
日期 ISO、查询参数显式声明、分页统一 PageResponse。
"""


def _get_schema(client):
    return client.get("/api/schema", HTTP_ACCEPT="application/json")


def test_schema_ok(client):
    r = _get_schema(client)
    assert r.status_code == 200
    data = r.json()
    assert data["openapi"].startswith("3.")
    assert "/api/v1/auth/me" in data["paths"]


def test_me_role_enum(client):
    """/auth/me 响应 schema 中 role 必须是 Choice 枚举。"""
    schema = _get_schema(client).json()
    me = schema["paths"]["/api/v1/auth/me"]["get"]
    resp = me["responses"]["200"]["content"]["application/json"]["schema"]
    # role 出现在组件引用或内联中——解析组件定义
    role_enum = _find_role_enum(schema, resp)
    assert role_enum == ["admin", "operator"], role_enum


def _find_role_enum(schema, node):
    """递归找 role 属性的 enum（兼容 $ref / allOf 包装）。"""
    seen = set()

    def resolve(n):
        """解析可能被 allOf/$ref 包装的 schema 节点，返回最终 dict。"""
        if isinstance(n, dict):
            if "$ref" in n:
                ref = n["$ref"]
                if ref in seen:
                    return {}
                seen.add(ref)
                _, _, name = ref.partition("components/schemas/")
                return resolve(schema["components"]["schemas"].get(name, {}))
            if "allOf" in n:
                merged = {k: v for k, v in n.items() if k != "allOf"}
                for sub in n["allOf"]:
                    merged.update(resolve(sub))
                return merged
            return n
        return {}

    def walk(n):
        if isinstance(n, dict):
            if "role" in n:
                role_node = resolve(n["role"])
                if "enum" in role_node:
                    return role_node["enum"]
            if "$ref" in n:
                sub = resolve(n)
                r = walk(sub)
                if r:
                    return r
            for v in n.values():
                r = walk(v)
                if r:
                    return r
        elif isinstance(n, list):
            for v in n:
                r = walk(v)
                if r:
                    return r
        return None

    return walk(node)


def test_docs_ui(client):
    r = client.get("/api/docs/")
    assert r.status_code == 200
    assert b"swagger" in r.content.lower()


def test_redoc(client):
    assert client.get("/api/redoc/").status_code == 200
