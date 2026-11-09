"""Local installation management with verified, installation-specific recovery."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import build as builder
import install as installer


def data_root():
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "RiichiCityStyle"


def legacy_data_root():
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "RiichiStyle"


def load_game():
    for folder in (data_root(), legacy_data_root()):
        try:
            value = json.loads((folder / "gui.json").read_text("utf8")).get("game", "")
            if isinstance(value, str) and value:
                return value
        except (OSError, ValueError, AttributeError):
            continue
    candidate = Path(os.environ.get("APPDATA", "")) / "RiichicityLauncher/Game"
    return str(candidate) if (candidate / "Mahjong-JP.exe").is_file() else ""


def normalize_game(value):
    game = Path(value).expanduser().resolve()
    if game.is_file() and game.name.lower() == "mahjong-jp.exe":
        game = game.parent
    if not (game / "Mahjong-JP.exe").is_file():
        raise ValueError("请选择包含 Mahjong-JP.exe 的 Game 目录，不要选择启动器。")
    return game


def choose_state(game, *, local=None, roaming=None, legacy=None):
    local = local or data_root()
    roaming = roaming or Path(os.environ.get("APPDATA", str(Path.home())))
    key = hashlib.sha256(str(game.resolve()).casefold().encode()).hexdigest()[:16]
    dedicated = local / "installs" / key
    target = installer.target_for(game)
    legacy_install = (legacy or legacy_data_root()) / "installs" / key
    for folder in [roaming / "akagiplus/riichicity-local", dedicated, legacy_install]:
        journal = folder / "install.json"
        if not journal.is_file():
            continue
        try:
            record = json.loads(journal.read_text("utf8"))
            owner = Path(record["target"]).resolve()
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise ValueError("恢复记录无法读取，请保留备份并先排查：" + str(journal)) from exc
        if owner == target:
            return folder
        if folder == dedicated:
            raise ValueError("恢复记录属于另一个安装目录。")
    return dedicated


def verified_record(game, journal):
    record = json.loads(journal.read_text("utf8"))
    if record.get("schema") != 1 or Path(record["target"]).resolve() != installer.target_for(game):
        raise ValueError("恢复记录与当前安装目录不匹配。")
    if record["original_sha256"] != builder.SOURCE_SHA256:
        raise ValueError("恢复记录的原始资源版本未适配。")
    if installer.digest(Path(record["backup"]).read_bytes()) != builder.SOURCE_SHA256:
        raise ValueError("原始备份校验失败，请保留备份目录。")
    current = installer.digest(installer.target_for(game).read_bytes())
    if current not in {record["original_sha256"], record["patched_sha256"], record.get("previous_sha256")}:
        raise ValueError("游戏文件已更新或被修改，停止覆盖。")
    return record


def payload():
    return Path(__file__).with_name("local_cosmetics.lua").read_text("utf-8-sig")


def status(game, state):
    current = installer.digest(installer.target_for(game).read_bytes())
    journal = state / "install.json"
    if journal.is_file():
        record = verified_record(game, journal)
        if current == record["patched_sha256"]:
            latest = installer.digest(payload().encode()) == record.get("payload_sha256")
            return {"status": "installed" if latest else "update_available", "message": "本地装扮已安装" + ("，当前核心已是最新。" if latest else "，可更新核心。")}
        if current != builder.SOURCE_SHA256:
            return {"status": "update_available", "message": "检测到之前的本地补丁，可重新安装或还原。"}
    if current != builder.SOURCE_SHA256:
        raise ValueError("当前客户端文件未适配，或缺少现有补丁的恢复记录。")
    return {"status": "not_installed", "message": "客户端资源已适配，尚未安装本地装扮。"}


def apply_patch(game, state):
    installer.ensure_closed()
    target = installer.target_for(game)
    current = target.read_bytes()
    journal = state / "install.json"
    original = current
    if journal.is_file():
        record = verified_record(game, journal)
        original = Path(record["backup"]).read_bytes()
    if installer.digest(original) != builder.SOURCE_SHA256:
        raise ValueError("未找到当前资源对应的原始备份，不能覆盖未知文件。")
    patched, changed = builder.build(original, payload())
    state.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="staged-", dir=state) as temporary:
        staged = Path(temporary) / "lua_network"
        staged.write_bytes(patched)
        staged.with_suffix(".manifest.json").write_text(json.dumps({"source_sha256": builder.SOURCE_SHA256, "patched_sha256": installer.digest(patched), "payload_sha256": installer.digest(payload().encode()), "changed_textassets": changed}), encoding="utf8")
        installer.install(game, staged, state / "backups", journal)


def perform(action, value):
    game = normalize_game(value)
    state = choose_state(game)
    if action == "install":
        apply_patch(game, state)
    elif action == "restore":
        installer.ensure_closed()
        if not (state / "install.json").is_file():
            raise ValueError("未找到这个安装目录的原始备份，不能还原。")
        verified_record(game, state / "install.json")
        installer.restore(game, state / "install.json")
    elif action != "status":
        raise ValueError("未知操作。")
    result = status(game, state)
    if action == "install":
        result["message"] = "安装 / 更新完成，重新启动游戏后生效。"
    elif action == "restore":
        result["message"] = "已还原游戏文件，本地装扮选择保留。"
    installer.atomic(data_root() / "gui.json", json.dumps({"game": str(game)}, ensure_ascii=False).encode("utf8"))
    return {**result, "game": str(game), "state": str(state)}


def friendly_error(error):
    message = str(error)
    if "Close RiichiCity" in message:
        return "请先正常退出一番街，再安装、更新或还原。"
    if "hot-update" in message:
        return "检测到尚未适配的热更新资源，请等待插件更新。"
    if "checksum" in message.lower():
        return "资源或备份校验失败，请保留当前文件与恢复记录。"
    if "Permission" in message or "WinError 5" in message:
        return "没有写入权限，请检查游戏目录权限后再试。"
    return message or type(error).__name__
