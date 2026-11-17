"""SmartHire 黑盒测试脚本。

测试对象：
  U 简历上传接口   POST /api/v1/resumes/upload
  B 账号认证接口   POST /api/v1/auth/register、POST /api/v1/auth/login

方法：等价类划分 + 边界值分析 + 错误推测。只通过 HTTP 请求与可观察响应
（状态码、响应体、列表可见记录、上传目录文件数）判定，不读取被测代码分支，
不修改被测代码。

运行：
  python 黑盒测试脚本.py

脚本会使用独立的临时数据库与上传目录，不触碰业务数据；
全部用例通过时退出码为 0，否则为 1。
"""

from __future__ import annotations

import asyncio
import csv
import io
import os
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path

BASE = Path(__file__).resolve().parent
BACKEND = BASE.parent / "NewRepo-main" / "backend"
RUN = BASE / "_run"

# ---------- 隔离运行环境：临时数据库、上传目录、关闭真实 AI ----------
if RUN.exists():
    shutil.rmtree(RUN)
(RUN / "uploads").mkdir(parents=True)
(RUN / "tmp").mkdir(parents=True)

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{(RUN / 'blackbox.db').as_posix()}"
os.environ["UPLOAD_DIR"] = str(RUN / "uploads")
os.environ["DEEPSEEK_API_KEY"] = ""
os.environ["SEED_ADMIN"] = "false"
os.environ["MAX_UPLOAD_SIZE"] = str(10 * 1024 * 1024)

sys.path.insert(0, str(BACKEND))

from loguru import logger  # noqa: E402

logger.remove()
logger.add(RUN / "backend.log", level="INFO", encoding="utf-8")

from httpx import ASGITransport, AsyncClient  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from sqlalchemy import update  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import User  # noqa: E402

OUTPUT = BASE / "执行结果.txt"
_REPORT: list[str] = []


def emit(text: str = "") -> None:
    """同时输出到控制台与执行结果文件（文件固定 UTF-8，避免控制台代码页影响）。"""
    _REPORT.append(text)
    print(text)


UPLOAD = "/api/v1/resumes/upload"
REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
MAX_SIZE = 10 * 1024 * 1024  # 需求 NFR02：单文件 10 MB
MAX_PIXELS = 25_000_000  # 需求 NFR02：图片 2500 万像素

# ---------- 测试数据构造 ----------


def text_file(size: int, fill: bytes = b"a") -> bytes:
    """构造指定字节数的文本内容。"""
    return fill * size


def png_bytes(text: str | None = None, size: tuple[int, int] = (1400, 200), fmt: str = "PNG") -> bytes:
    """生成图片；text 为 None 时是空白图。"""
    image = Image.new("RGB", size, "white")
    if text:
        draw = ImageDraw.Draw(image)
        draw.text((30, 40), text, font=ImageFont.load_default(size=48), fill="black")
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    return buffer.getvalue()


def docx_bytes() -> bytes:
    from docx import Document

    path = RUN / "tmp" / "resume.docx"
    document = Document()
    document.add_paragraph("Python 后端工程师")
    document.add_paragraph("熟悉 FastAPI、SQLAlchemy 与 PostgreSQL")
    document.save(path)
    return path.read_bytes()


def pdf_bytes() -> bytes:
    """手工构造一个最小可解析 PDF（含一行文字）。"""
    stream = b"BT /F1 12 Tf 72 720 Td (Python FastAPI engineer) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode() + b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(out)


def raw_multipart(field: str, filename: str, content: bytes, boundary: str = "BB") -> tuple[dict, bytes]:
    """手工拼 multipart，用于发送普通客户端无法发出的原始文件名。"""
    head = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode("latin-1")
    return {"Content-Type": f"multipart/form-data; boundary={boundary}"}, head + content + f"\r\n--{boundary}--\r\n".encode()


# ---------- 响应观察工具 ----------


def detail_text(response) -> str:
    """抽取可观察的错误信息：FastAPI 的 dict 或 Pydantic 校验列表。"""
    try:
        data = response.json()
    except Exception:
        return response.text[:120]
    if not isinstance(data, dict):
        return str(data)[:120]
    detail = data.get("detail")
    if isinstance(detail, list):
        parts = []
        for item in detail:
            if isinstance(item, dict):
                loc = ".".join(str(x) for x in item.get("loc", []))
                parts.append(f"{loc}: {item.get('msg', '')}".strip(": "))
            else:
                parts.append(str(item))
        return "；".join(parts)[:200]
    if detail is None:
        return str(data)[:120]
    return str(detail)[:200]


def observe(response, extra: str | None = None) -> str:
    text = f"{response.status_code} {detail_text(response)}".strip()
    if extra:
        text += f"｜{extra}"
    return text[:220]


def status_is(response, expected: int, needle: str | None = None) -> bool:
    ok = response.status_code == expected
    if needle is not None:
        ok = ok and needle in detail_text(response)
    return ok


# ---------- 用例注册 ----------


@dataclass
class Case:
    cid: str
    obj: str
    dim: str
    tech: str
    point: str
    inp: str
    expect: str
    fn: object = None


CASES: list[Case] = []


def case(cid: str, obj: str, dim: str, tech: str, point: str, inp: str, expect: str):
    def wrap(fn):
        CASES.append(Case(cid, obj, dim, tech, point, inp, expect, fn))
        return fn

    return wrap


# ================= 被测对象 U：简历上传接口 =================


@case("U01", "U 简历上传", "A1 身份与令牌", "等价类-无效", "未认证用户（无 Authorization 头）", "不带令牌上传 a.txt", "401；Not authenticated")
async def _(api, ctx):
    r = await api.post(UPLOAD, files={"file": ("a.txt", b"hello")})
    return status_is(r, 401, "Not authenticated"), observe(r)


@case("U02", "U 简历上传", "A1 身份与令牌", "等价类-无效", "令牌格式非法（并非 JWT）", "Bearer not-a-jwt 上传 a.txt", "401；Invalid token")
async def _(api, ctx):
    r = await api.post(
        UPLOAD, headers={"Authorization": "Bearer not-a-jwt"}, files={"file": ("a.txt", b"hello")}
    )
    return status_is(r, 401, "Invalid token"), observe(r)


@case("U03", "U 简历上传", "A1 身份与令牌", "等价类-无效", "令牌类型错误（刷新令牌不能当访问令牌）", "用 login 返回的 refresh_token 上传 a.txt", "401；Invalid token")
async def _(api, ctx):
    r = await api.post(
        UPLOAD,
        headers={"Authorization": f"Bearer {ctx['refresh']}"},
        files={"file": ("a.txt", b"hello")},
    )
    return status_is(r, 401, "Invalid token"), observe(r)


@case("U04", "U 简历上传", "A1 身份与令牌", "等价类-有效", "已登录 HR 账号", "HR 令牌上传 a.txt", "201；status=PARSED")
async def _(api, ctx):
    r = await api.post(UPLOAD, headers=ctx["hr"], files={"file": ("a.txt", b"Python engineer")})
    ok = status_is(r, 201) and r.json().get("status") == "PARSED"
    return ok, observe(r, f"status={r.json().get('status')}" if r.status_code == 201 else None)


@case("U05", "U 简历上传", "A1 身份与令牌", "等价类-有效", "已登录求职者账号（上传不限角色）", "JOB_SEEKER 令牌上传 a.txt", "201；status=PARSED")
async def _(api, ctx):
    r = await api.post(UPLOAD, headers=ctx["seeker"], files={"file": ("a.txt", b"Python engineer")})
    ok = status_is(r, 201) and r.json().get("status") == "PARSED"
    return ok, observe(r, f"status={r.json().get('status')}" if r.status_code == 201 else None)


@case("U06", "U 简历上传", "A2 请求体结构", "错误推测", "非 multipart 请求（JSON 体）", "POST JSON {\"file\":\"x\"}", "422；缺少 file 字段")
async def _(api, ctx):
    r = await api.post(UPLOAD, headers=ctx["hr"], json={"file": "x"})
    return status_is(r, 422, "file"), observe(r)


@case("U07", "U 简历上传", "A2 请求体结构", "错误推测", "文件字段名错误", "字段名用 document 而非 file", "422；缺少 file 字段")
async def _(api, ctx):
    r = await api.post(
        UPLOAD, headers=ctx["hr"], files={"document": ("a.txt", b"hello")}
    )
    return status_is(r, 422, "file"), observe(r)


@case("U08", "U 简历上传", "A2 请求体结构", "错误推测", "文件名为空（退化为普通表单字段）", "filename=\"\" 上传内容 hello", "422；缺少 file 字段")
async def _(api, ctx):
    r = await api.post(UPLOAD, headers=ctx["hr"], files={"file": ("", b"hello")})
    return status_is(r, 422, "file"), observe(r)


@case("U09", "U 简历上传", "A3 文件扩展名", "等价类-有效", "白名单 .txt", "a.txt 文本内容", "201；PARSED")
async def _(api, ctx):
    r = await api.post(UPLOAD, headers=ctx["hr"], files={"file": ("a.txt", b"Python engineer")})
    return status_is(r, 201), observe(r)


@case("U10", "U 简历上传", "A3 文件扩展名", "等价类-有效", "大写扩展名（应统一转小写）", "a.TXT 文本内容", "201；PARSED")
async def _(api, ctx):
    r = await api.post(UPLOAD, headers=ctx["hr"], files={"file": ("a.TXT", b"Python engineer")})
    return status_is(r, 201), observe(r)


@case("U11", "U 简历上传", "A3 文件扩展名", "等价类-有效", "白名单 .md", "a.md 文本内容", "201；PARSED")
async def _(api, ctx):
    r = await api.post(UPLOAD, headers=ctx["hr"], files={"file": ("a.md", b"# Python engineer")})
    return status_is(r, 201), observe(r)


@case("U12", "U 简历上传", "A3 文件扩展名", "等价类-有效", "白名单 .markdown", "a.markdown 文本内容", "201；PARSED")
async def _(api, ctx):
    r = await api.post(UPLOAD, headers=ctx["hr"], files={"file": ("a.markdown", b"# Python engineer")})
    return status_is(r, 201), observe(r)


@case("U13", "U 简历上传", "A3 文件扩展名", "等价类-有效", "白名单 .pdf（内容为真实可解析 PDF）", "ok.pdf", "201；PARSED")
async def _(api, ctx):
    r = await api.post(UPLOAD, headers=ctx["hr"], files={"file": ("ok.pdf", pdf_bytes())})
    return status_is(r, 201), observe(r)


@case("U14", "U 简历上传", "A3 文件扩展名", "等价类-有效", "白名单 .docx（内容为真实 Word 文档）", "ok.docx", "201；PARSED")
async def _(api, ctx):
    r = await api.post(UPLOAD, headers=ctx["hr"], files={"file": ("ok.docx", docx_bytes())})
    return status_is(r, 201), observe(r)


@case("U15", "U 简历上传", "A3 文件扩展名", "等价类-有效", "白名单 .png（真实含文字图片，走本地 OCR）", "text.png 1400×200 含英文文字", "201；原文非空")
async def _(api, ctx):
    r = await api.post(
        UPLOAD,
        headers=ctx["hr"],
        files={"file": ("text.png", png_bytes("Python FastAPI PostgreSQL"))},
    )
    raw = ""
    if r.status_code == 201:
        detail = await api.get(f"/api/v1/resumes/{r.json()['id']}", headers=ctx["hr"])
        raw = detail.json().get("raw_text") or ""
    return status_is(r, 201) and bool(raw.strip()), observe(r, f"原文长度={len(raw)}")


@case("U16", "U 简历上传", "A3 文件扩展名", "等价类-有效", "白名单 .jpg（内容合法但无文字）", "blank.jpg 800×120 空白图", "422；未识别到文字（说明格式已验证通过）")
async def _(api, ctx):
    r = await api.post(
        UPLOAD, headers=ctx["hr"], files={"file": ("blank.jpg", png_bytes(size=(800, 120), fmt="JPEG"))}
    )
    return status_is(r, 422, "未识别到文字"), observe(r)


@case("U17", "U 简历上传", "A3 文件扩展名", "等价类-有效", "白名单 .jpeg（内容合法但无文字）", "blank.jpeg 800×120 空白图", "422；未识别到文字")
async def _(api, ctx):
    r = await api.post(
        UPLOAD, headers=ctx["hr"], files={"file": ("blank.jpeg", png_bytes(size=(800, 120), fmt="JPEG"))}
    )
    return status_is(r, 422, "未识别到文字"), observe(r)


@case("U18", "U 简历上传", "A3 文件扩展名", "等价类-有效", "白名单 .webp（内容合法但无文字）", "blank.webp 800×120 空白图", "422；未识别到文字")
async def _(api, ctx):
    r = await api.post(
        UPLOAD, headers=ctx["hr"], files={"file": ("blank.webp", png_bytes(size=(800, 120), fmt="WEBP"))}
    )
    return status_is(r, 422, "未识别到文字"), observe(r)


@case("U19", "U 简历上传", "A3 文件扩展名", "等价类-有效", "白名单 .bmp（内容合法但无文字）", "blank.bmp 800×120 空白图", "422；未识别到文字")
async def _(api, ctx):
    r = await api.post(
        UPLOAD, headers=ctx["hr"], files={"file": ("blank.bmp", png_bytes(size=(800, 120), fmt="BMP"))}
    )
    return status_is(r, 422, "未识别到文字"), observe(r)


@case("U20", "U 简历上传", "A3 文件扩展名", "等价类-无效", "老版 Word 不在白名单", "a.doc", "400；Unsupported file type")
async def _(api, ctx):
    r = await api.post(UPLOAD, headers=ctx["hr"], files={"file": ("a.doc", b"hello")})
    return status_is(r, 400, "Unsupported file type"), observe(r)


@case("U21", "U 简历上传", "A3 文件扩展名", "等价类-无效", "可执行文件不在白名单", "a.exe", "400；Unsupported file type")
async def _(api, ctx):
    r = await api.post(UPLOAD, headers=ctx["hr"], files={"file": ("a.exe", b"hello")})
    return status_is(r, 400, "Unsupported file type"), observe(r)


@case("U22", "U 简历上传", "A3 文件扩展名", "等价类-无效", "表格文件不在白名单", "a.csv", "400；Unsupported file type")
async def _(api, ctx):
    r = await api.post(UPLOAD, headers=ctx["hr"], files={"file": ("a.csv", b"hello")})
    return status_is(r, 400, "Unsupported file type"), observe(r)


@case("U23", "U 简历上传", "A3 文件扩展名", "边界值-无效", "无扩展名", "resume（无点号后缀）", "400；Unsupported file type ''")
async def _(api, ctx):
    r = await api.post(UPLOAD, headers=ctx["hr"], files={"file": ("resume", b"hello")})
    return status_is(r, 400, "Unsupported file type"), observe(r)


@case("U24", "U 简历上传", "A3 文件扩展名", "边界值-无效", "只有点号、没有主名", ".txt", "400；Unsupported file type ''")
async def _(api, ctx):
    r = await api.post(UPLOAD, headers=ctx["hr"], files={"file": (".txt", b"hello")})
    return status_is(r, 400, "Unsupported file type"), observe(r)


@case("U25", "U 简历上传", "A3 文件扩展名", "边界值-无效", "扩展名带尾随空格", "\"a.txt \"（末尾一个空格）", "400；Unsupported file type '.txt '")
async def _(api, ctx):
    r = await api.post(UPLOAD, headers=ctx["hr"], files={"file": ("a.txt ", b"hello")})
    return status_is(r, 400, "Unsupported file type"), observe(r)


@case("U26", "U 简历上传", "A4 文件大小", "边界值-下界", "0 字节空文件", "empty.txt 0 字节", "422；未识别到文字")
async def _(api, ctx):
    r = await api.post(UPLOAD, headers=ctx["hr"], files={"file": ("empty.txt", b"")})
    return status_is(r, 422, "未识别到文字"), observe(r)


@case("U27", "U 简历上传", "A4 文件大小", "边界值-下界", "1 字节最小非空文件", "one.txt 内容 \"a\"", "201；PARSED")
async def _(api, ctx):
    r = await api.post(UPLOAD, headers=ctx["hr"], files={"file": ("one.txt", b"a")})
    return status_is(r, 201), observe(r)


@case("U28", "U 简历上传", "A4 文件大小", "错误推测", "只有空白的文本（不可作为简历正文）", "space.txt 内容为空格换行制表符", "422；未识别到文字")
async def _(api, ctx):
    r = await api.post(UPLOAD, headers=ctx["hr"], files={"file": ("space.txt", b"  \n\t  ")})
    return status_is(r, 422, "未识别到文字"), observe(r)


@case("U29", "U 简历上传", "A4 文件大小", "边界值-上界", "恰好 10 MB（10 485 760 字节）", "exact10m.txt 10 MB", "201；PARSED")
async def _(api, ctx):
    r = await api.post(UPLOAD, headers=ctx["hr"], files={"file": ("exact10m.txt", text_file(MAX_SIZE))})
    return status_is(r, 201), observe(r, f"字节={MAX_SIZE}")


@case("U30", "U 简历上传", "A4 文件大小", "边界值-越界", "10 MB + 1 字节", "over10m.txt 10 485 761 字节", "413；File too large")
async def _(api, ctx):
    r = await api.post(
        UPLOAD, headers=ctx["hr"], files={"file": ("over10m.txt", text_file(MAX_SIZE + 1))}
    )
    return status_is(r, 413, "File too large"), observe(r, f"字节={MAX_SIZE + 1}")


@case("U31", "U 简历上传", "A5 文件名", "边界值-上界", "文件名长度恰好 255 字符", "\"n\"×251 + \".txt\"", "201；标题完整保留 255 字符")
async def _(api, ctx):
    name = "n" * 251 + ".txt"
    r = await api.post(UPLOAD, headers=ctx["hr"], files={"file": (name, b"Python engineer")})
    ok = status_is(r, 201) and r.json().get("title") == name
    return ok, observe(r, f"标题长度={len(r.json().get('title', '')) if r.status_code == 201 else 0}")


@case("U32", "U 简历上传", "A5 文件名", "边界值-越界", "文件名长度 256 字符", "\"n\"×252 + \".txt\"", "400；Invalid filename")
async def _(api, ctx):
    r = await api.post(
        UPLOAD, headers=ctx["hr"], files={"file": ("n" * 252 + ".txt", b"Python engineer")}
    )
    return status_is(r, 400, "Invalid filename"), observe(r)


@case("U33", "U 简历上传", "A5 文件名", "等价类-无效", "文件名含控制字符（需手工构造 multipart）", "filename=\"bad\\x01name.txt\"", "400；Invalid filename")
async def _(api, ctx):
    headers, body = raw_multipart("file", "bad\x01name.txt", b"hello")
    r = await api.post(UPLOAD, headers={**ctx["hr"], **headers}, content=body)
    return status_is(r, 400, "Invalid filename"), observe(r)


@case("U34", "U 简历上传", "A5 文件名", "错误推测", "路径穿越文件名", "\"..\\\\..\\\\escape.txt\"", "201；标题归一为 escape.txt，文件不逃逸上传目录")
async def _(api, ctx):
    r = await api.post(UPLOAD, headers=ctx["hr"], files={"file": ("..\\..\\escape.txt", b"hello")})
    escaped = (RUN / "escape.txt").exists() or (BASE / "escape.txt").exists()
    ok = status_is(r, 201) and r.json().get("title") == "escape.txt" and not escaped
    return ok, observe(r, f"标题={r.json().get('title') if r.status_code == 201 else '-'}；目录外文件={escaped}")


@case("U35", "U 简历上传", "A5 文件名", "错误推测", "绝对路径文件名", "\"C:\\\\Windows\\\\abs.txt\"", "201；标题归一为 abs.txt")
async def _(api, ctx):
    r = await api.post(
        UPLOAD, headers=ctx["hr"], files={"file": ("C:\\Windows\\abs.txt", b"hello")}
    )
    ok = status_is(r, 201) and r.json().get("title") == "abs.txt"
    return ok, observe(r, f"标题={r.json().get('title') if r.status_code == 201 else '-'}")


@case("U36", "U 简历上传", "A5 文件名", "等价类-有效", "中文文件名", "中文简历.txt", "201；标题保留中文名")
async def _(api, ctx):
    r = await api.post(
        UPLOAD, headers=ctx["hr"], files={"file": ("中文简历.txt", "软件工程师 简历".encode())}
    )
    ok = status_is(r, 201) and r.json().get("title") == "中文简历.txt"
    return ok, observe(r, f"标题={r.json().get('title') if r.status_code == 201 else '-'}")


@case("U37", "U 简历上传", "A6 图片内容与像素", "边界值-上界", "恰好 2500 万像素（5000×5000）", "limit.png 空白", "422；未识别到文字（说明像素校验通过）")
async def _(api, ctx):
    r = await api.post(UPLOAD, headers=ctx["hr"], files={"file": ("limit.png", png_bytes(size=(5000, 5000)))})
    return status_is(r, 422, "未识别到文字"), observe(r, f"像素={MAX_PIXELS}")


@case("U38", "U 简历上传", "A6 图片内容与像素", "边界值-越界", "2500 万 + 1 像素（5000×5001）", "over.png 空白", "422；提示分辨率过大")
async def _(api, ctx):
    r = await api.post(UPLOAD, headers=ctx["hr"], files={"file": ("over.png", png_bytes(size=(5000, 5001)))})
    return status_is(r, 422, "分辨率过大"), observe(r, f"像素={MAX_PIXELS + 5000}")


@case("U39", "U 简历上传", "A6 图片内容与像素", "错误推测", "扩展名合法但内容损坏", "broken.jpg 内容为文本", "422；图片损坏")
async def _(api, ctx):
    r = await api.post(UPLOAD, headers=ctx["hr"], files={"file": ("broken.jpg", b"not an image")})
    return status_is(r, 422, "图片损坏"), observe(r)


@case("U40", "U 简历上传", "A6 图片内容与像素", "错误推测", "真实格式不在支持集合（GIF 改 .png 后缀）", "renamed.png 实为 GIF", "422；图片格式不受支持")
async def _(api, ctx):
    r = await api.post(
        UPLOAD, headers=ctx["hr"], files={"file": ("renamed.png", png_bytes("hello", size=(120, 60), fmt="GIF"))}
    )
    return status_is(r, 422, "图片格式不受支持"), observe(r)


@case("U41", "U 简历上传", "A7 可见后置条件", "等价类-有效", "上传成功后记录可见", "上传 visible.txt 后查询简历列表", "201 且列表含该记录，标题与状态正确")
async def _(api, ctx):
    r = await api.post(UPLOAD, headers=ctx["hr"], files={"file": ("visible.txt", b"Python engineer")})
    if r.status_code != 201:
        return False, observe(r)
    rid = r.json()["id"]
    rows = (await api.get("/api/v1/resumes/", headers=ctx["hr"])).json()
    hit = next((row for row in rows if row["id"] == rid), None)
    ok = bool(hit) and hit["title"] == "visible.txt" and hit["status"] == "PARSED"
    return ok, observe(r, f"列表命中={bool(hit)}；状态={hit['status'] if hit else '-'}")


@case("U42", "U 简历上传", "A7 可见后置条件", "错误推测", "同名文件重复上传", "同一文件名上传两次", "201 两次；两条独立记录，ID 不同")
async def _(api, ctx):
    first = await api.post(UPLOAD, headers=ctx["hr"], files={"file": ("same.txt", b"first")})
    second = await api.post(UPLOAD, headers=ctx["hr"], files={"file": ("same.txt", b"second")})
    if first.status_code != 201 or second.status_code != 201:
        return False, observe(second)
    rows = (await api.get("/api/v1/resumes/", headers=ctx["hr"])).json()
    same = [row for row in rows if row["title"] == "same.txt"]
    ok = first.json()["id"] != second.json()["id"] and len(same) == 2
    return ok, observe(second, f"同名记录数={len(same)}；ID 不同={first.json()['id'] != second.json()['id']}")


@case("U43", "U 简历上传", "A7 可见后置条件", "错误推测", "解析失败的上传不落库、不残留文件", "上传无法解析的 bad.pdf", "422；记录数与上传目录文件数均不变")
async def _(api, ctx):
    before_rows = len((await api.get("/api/v1/resumes/", headers=ctx["hr"])).json())
    before_files = len(list((RUN / "uploads").iterdir()))
    r = await api.post(UPLOAD, headers=ctx["hr"], files={"file": ("bad.pdf", b"%PDF-1.4 broken")})
    after_rows = len((await api.get("/api/v1/resumes/", headers=ctx["hr"])).json())
    after_files = len(list((RUN / "uploads").iterdir()))
    ok = status_is(r, 422) and before_rows == after_rows and before_files == after_files
    return ok, observe(r, f"记录 {before_rows}→{after_rows}；文件 {before_files}→{after_files}")


# ================= 被测对象 B：账号认证接口 =================


async def register(api, username, email, password, role="HR"):
    payload = {"username": username, "email": email, "password": password}
    if role is not None:
        payload["role"] = role
    return await api.post(REGISTER, json=payload)


@case("B01", "B 账号认证", "B1 用户名长度", "边界值-下界", "用户名 2 字符（下限 -1）", "username=\"ab\"", "422；用户名至少 3 字符")
async def _(api, ctx):
    r = await register(api, "ab", "b01@bbmail.com", "secret123")
    return status_is(r, 422, "username"), observe(r)


@case("B02", "B 账号认证", "B1 用户名长度", "边界值-下界", "用户名 3 字符（下限）", "username=\"b02\"", "201；注册成功")
async def _(api, ctx):
    r = await register(api, "b02", "b02@bbmail.com", "secret123")
    ok = status_is(r, 201) and r.json().get("username") == "b02"
    return ok, observe(r)


@case("B03", "B 账号认证", "B1 用户名长度", "边界值-上界", "用户名 50 字符（上限）", "\"u\"×50", "201；注册成功")
async def _(api, ctx):
    name = "u" * 50
    r = await register(api, name, "b03@bbmail.com", "secret123")
    ok = status_is(r, 201) and r.json().get("username") == name
    return ok, observe(r, f"用户名长度={len(r.json().get('username', '')) if r.status_code == 201 else 0}")


@case("B04", "B 账号认证", "B1 用户名长度", "边界值-越界", "用户名 51 字符（上限 +1）", "\"u\"×51", "422；用户名最多 50 字符")
async def _(api, ctx):
    r = await register(api, "u" * 51, "b04@bbmail.com", "secret123")
    return status_is(r, 422, "username"), observe(r)


@case("B05", "B 账号认证", "B2 密码长度", "边界值-下界", "密码 5 字符（下限 -1）", "password=\"abcde\"", "422；密码至少 6 字符")
async def _(api, ctx):
    r = await register(api, "b05user", "b05@bbmail.com", "abcde")
    return status_is(r, 422, "password"), observe(r)


@case("B06", "B 账号认证", "B2 密码长度", "边界值-下界", "密码 6 字符（下限）", "password=\"abcdef\"", "201；注册成功")
async def _(api, ctx):
    r = await register(api, "b06user", "b06@bbmail.com", "abcdef")
    return status_is(r, 201), observe(r)


@case("B07", "B 账号认证", "B2 密码长度", "边界值-上界", "密码 128 字符（上限）", "\"p\"×128", "201；注册成功")
async def _(api, ctx):
    r = await register(api, "b07user", "b07@bbmail.com", "p" * 128)
    return status_is(r, 201), observe(r, "密码长度=128")


@case("B08", "B 账号认证", "B2 密码长度", "边界值-越界", "密码 129 字符（上限 +1）", "\"p\"×129", "422；密码最多 128 字符")
async def _(api, ctx):
    r = await register(api, "b08user", "b08@bbmail.com", "p" * 129)
    return status_is(r, 422, "password"), observe(r)


@case("B09", "B 账号认证", "B3 邮箱格式", "等价类-无效", "缺少 @ 的邮箱", "\"not-an-email\"", "422；邮箱格式非法")
async def _(api, ctx):
    r = await register(api, "b09user", "not-an-email", "secret123")
    return status_is(r, 422, "email"), observe(r)


@case("B10", "B 账号认证", "B3 邮箱格式", "等价类-无效", "只有 @ 没有域名", "\"b10@\"", "422；邮箱格式非法")
async def _(api, ctx):
    r = await register(api, "b10user", "b10@", "secret123")
    return status_is(r, 422, "email"), observe(r)


@case("B11", "B 账号认证", "B4 角色枚举", "等价类-无效", "不存在的角色", "role=\"ADMIN\"", "422；角色只能是 HR 或 JOB_SEEKER")
async def _(api, ctx):
    r = await register(api, "b11user", "b11@bbmail.com", "secret123", role="ADMIN")
    return status_is(r, 422, "role"), observe(r)


@case("B12", "B 账号认证", "B4 角色枚举", "等价类-无效", "小写角色（枚举区分大小写）", "role=\"hr\"", "422；角色只能是 HR 或 JOB_SEEKER")
async def _(api, ctx):
    r = await register(api, "b12user", "b12@bbmail.com", "secret123", role="hr")
    return status_is(r, 422, "role"), observe(r)


@case("B13", "B 账号认证", "B4 角色枚举", "等价类-有效", "省略角色（取默认值）", "不传 role 字段", "201；role=JOB_SEEKER")
async def _(api, ctx):
    r = await register(api, "b13user", "b13@bbmail.com", "secret123", role=None)
    ok = status_is(r, 201) and r.json().get("role") == "JOB_SEEKER"
    return ok, observe(r, f"role={r.json().get('role') if r.status_code == 201 else '-'}")


@case("B14", "B 账号认证", "B5 唯一性", "等价类-无效", "用户名已被占用", "重复注册同名账号 b14dup", "409；Username already taken")
async def _(api, ctx):
    await register(api, "b14dup", "b14a@bbmail.com", "secret123")
    r = await register(api, "b14dup", "b14b@bbmail.com", "secret123")
    return status_is(r, 409, "Username already taken"), observe(r)


@case("B15", "B 账号认证", "B5 唯一性", "等价类-无效", "邮箱已被注册", "两个用户名使用同一邮箱", "409；Email already registered")
async def _(api, ctx):
    await register(api, "b15a", "shared@bbmail.com", "secret123")
    r = await register(api, "b15b", "shared@bbmail.com", "secret123")
    return status_is(r, 409, "Email already registered"), observe(r)


@case("B16", "B 账号认证", "B6 必填字段", "错误推测", "只提供用户名", "请求体缺 email 与 password", "422；提示 email、password 必填")
async def _(api, ctx):
    r = await api.post(REGISTER, json={"username": "b16user"})
    detail = detail_text(r)
    ok = r.status_code == 422 and "email" in detail and "password" in detail
    return ok, observe(r)


@case("B17", "B 账号认证", "B7 登录凭证", "等价类-有效", "正确的用户名与密码", "用已注册账号登录", "200；返回 access/refresh 令牌，token_type=bearer")
async def _(api, ctx):
    r = await api.post(LOGIN, json={"username": "bb_hr", "password": "secret123"})
    body = r.json() if r.status_code == 200 else {}
    ok = (
        status_is(r, 200)
        and bool(body.get("access_token"))
        and bool(body.get("refresh_token"))
        and body.get("token_type") == "bearer"
    )
    return ok, observe(r, f"token_type={body.get('token_type')}")


@case("B18", "B 账号认证", "B7 登录凭证", "等价类-无效", "密码错误", "bb_hr + wrong-password", "401；Invalid username or password")
async def _(api, ctx):
    r = await api.post(LOGIN, json={"username": "bb_hr", "password": "wrong-password"})
    return status_is(r, 401, "Invalid username or password"), observe(r)


@case("B19", "B 账号认证", "B7 登录凭证", "等价类-无效", "账号不存在", "ghost_user + 任意密码", "401；Invalid username or password")
async def _(api, ctx):
    r = await api.post(LOGIN, json={"username": "ghost_user", "password": "secret123"})
    return status_is(r, 401, "Invalid username or password"), observe(r)


@case("B20", "B 账号认证", "B7 登录凭证", "等价类-无效", "用户名大小写不同", "BB_HR + 正确密码", "401；用户名区分大小写")
async def _(api, ctx):
    r = await api.post(LOGIN, json={"username": "BB_HR", "password": "secret123"})
    return status_is(r, 401, "Invalid username or password"), observe(r)


@case("B21", "B 账号认证", "B7 登录凭证", "等价类-无效", "账号已停用", "停用后使用正确密码登录", "403；Account is deactivated")
async def _(api, ctx):
    await register(api, "b21user", "b21@bbmail.com", "secret123")
    async with ctx["Session"]() as session:
        await session.execute(update(User).where(User.username == "b21user").values(is_active=False))
        await session.commit()
    r = await api.post(LOGIN, json={"username": "b21user", "password": "secret123"})
    return status_is(r, 403, "deactivated"), observe(r)


@case("B22", "B 账号认证", "B8 登录必填", "错误推测", "登录缺少密码", "{\"username\":\"bb_hr\"}", "422；提示 password 必填")
async def _(api, ctx):
    r = await api.post(LOGIN, json={"username": "bb_hr"})
    return status_is(r, 422, "password"), observe(r)


# ---------- 执行器 ----------


async def sign_in(api, username, password):
    response = await api.post(LOGIN, json={"username": username, "password": password})
    if response.status_code != 200:
        raise RuntimeError(f"测试前置登录失败：{username} -> {response.status_code} {response.text}")
    return response.json()


async def main() -> int:
    emit("=" * 78)
    emit("SmartHire 黑盒测试")
    emit("=" * 78)
    emit(f"Python        : {sys.version.split()[0]}")
    emit("被测服务      : FastAPI 应用（ASGI 传输，与真实 HTTP 请求同一路由与校验）")
    emit(f"数据库        : 独立临时 SQLite  {RUN / 'blackbox.db'}")
    emit(f"上传目录      : {RUN / 'uploads'}")
    emit(f"单文件上限    : {settings.MAX_UPLOAD_SIZE} 字节（10 MB）")
    emit("AI 密钥       : 未配置（上传只做文本提取，不调用模型）")

    engine = create_async_engine(f"sqlite+aiosqlite:///{(RUN / 'blackbox.db').as_posix()}")
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async def test_db():
        async with Session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    app.dependency_overrides[get_db] = test_db

    results = []
    started = time.perf_counter()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://blackbox") as api:
        # 前置：HR 与求职者各一个账号
        for username, role in [("bb_hr", "HR"), ("bb_seeker", "JOB_SEEKER")]:
            created = await register(api, username, f"{username}@bbmail.com", "secret123", role=role)
            if created.status_code != 201:
                raise RuntimeError(
                    f"测试前置注册失败：{username} -> {created.status_code} {created.text}"
                )
        hr_token = await sign_in(api, "bb_hr", "secret123")
        seeker_token = await sign_in(api, "bb_seeker", "secret123")
        ctx = {
            "hr": {"Authorization": f"Bearer {hr_token['access_token']}"},
            "seeker": {"Authorization": f"Bearer {seeker_token['access_token']}"},
            "refresh": hr_token["refresh_token"],
            "Session": Session,
        }

        emit("\n" + "-" * 78)
        emit("用例执行")
        emit("-" * 78)
        for item in CASES:
            t0 = time.perf_counter()
            try:
                ok, actual = await item.fn(api, ctx)
            except Exception as error:  # 一条用例异常不中断整轮
                ok, actual = False, f"抛出异常：{type(error).__name__}: {error}"
            elapsed = time.perf_counter() - t0
            results.append({**item.__dict__, "ok": ok, "actual": actual, "seconds": elapsed})
            flag = "通过" if ok else "失败"
            emit(f"{item.cid} [{flag}] {item.dim}｜{item.inp} → {actual}")

    app.dependency_overrides.clear()
    await engine.dispose()
    total = time.perf_counter() - started

    # ---------- 汇总 ----------
    passed = sum(1 for r in results if r["ok"])
    emit("\n" + "-" * 78)
    emit("覆盖汇总")
    emit("-" * 78)
    for obj in ["U 简历上传", "B 账号认证"]:
        subset = [r for r in results if r["obj"] == obj]
        emit(f"{obj}：{sum(1 for r in subset if r['ok'])}/{len(subset)} 通过")
    by_tech: dict[str, list] = {}
    for row in results:
        by_tech.setdefault(row["tech"], []).append(row)
    for tech, rows in by_tech.items():
        emit(f"  {tech}：{sum(1 for r in rows if r['ok'])}/{len(rows)}")

    emit("\n" + "-" * 78)
    emit("结论")
    emit("-" * 78)
    emit(f"用例总数 {len(results)}，通过 {passed}，失败 {len(results) - passed}，耗时 {total:.1f} 秒")
    if passed != len(results):
        for row in results:
            if not row["ok"]:
                emit(f"  失败 {row['cid']}：期望 {row['expect']}；实际 {row['actual']}")
    else:
        emit("全部用例的观察结果与期望一致。")

    # ---------- 导出 CSV ----------
    csv_path = BASE / "测试用例.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["用例编号", "被测对象", "输入维度", "设计方法", "等价类或边界值", "输入摘要", "期望结果", "实际结果", "结论"]
        )
        for row in results:
            writer.writerow(
                [
                    row["cid"],
                    row["obj"],
                    row["dim"],
                    row["tech"],
                    row["point"],
                    row["inp"],
                    row["expect"],
                    row["actual"],
                    "通过" if row["ok"] else "失败",
                ]
            )
    emit(f"\n用例明细已写入：{csv_path}")

    OUTPUT.write_text("\n".join(_REPORT) + "\n", encoding="utf-8")
    print(f"\n执行结果已写入：{OUTPUT}")

    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
