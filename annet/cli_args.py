# pylint: disable=too-many-ancestors

import abc
import argparse
import enum
import os

from valkit.common import valid_string_list

from annet.argparse import Arg, ArgGroup, DefaultFromEnv
from annet.hardware import hardware_connector
from annet.storage import Query, storage_connector


# ====
def valid_vendor(vendor):
    hw_provider = hardware_connector.get()
    hw = hw_provider.vendor_to_hw(vendor)
    if hw:
        return hw.vendor
    return ""


def convert_to_none(arg):
    return None if arg == "-" else arg


def valid_config_source(value):
    if value not in ["cfglister", "running", "empty", "-"] and not os.path.exists(value):
        raise ValueError("No such file or directory %r" % value)
    return value


def valid_range(value: str):
    if value.isdigit():
        return slice(0, int(value))
    elif ":" in value:
        start_str, stop_str = value.split(":", 1)
        if not stop_str:
            stop = None
        else:
            stop = int(stop_str)
        return slice(int(start_str), stop)

    raise ValueError("Invalid range: %s" % value)


def opt_query_factory(**kwargs):
    return Arg(
        "query",
        help="Запрос, определяющий список устройств. Принимается fqdn, rackcode, глоб"
             " или путь к файлу со списком запросов (нужно писать @path/to/file)",
        **kwargs,
    )


# ====
opt_query = opt_query_factory(nargs="+")

opt_query_optional = opt_query_factory(nargs="*", default=[])

opt_dest = Arg(
    "--dest", type=convert_to_none,
    help="Файл или каталог для вывода сгенерированных данных"
)

opt_expand_path = Arg(
    "--expand-path", default=False,
    help="Разворачивать пути entire-генераторов при записи их на файловую систему"
)

opt_old = Arg(
    "old",
    help="Файл со старым конфигом (или каталог с пачкой)"
)

opt_new = Arg(
    "new",
    help="Файл с новым конфигом (или каталог с пачкой)"
)

opt_hw = Arg(
    "--hw", default="", type=valid_vendor,
    help="Производитель устройства (например Huawei или Cisco) или полное название модели. Если его нет - пытаемся его задетектить"
)

opt_indent = Arg(
    "--indent", default="  ",
    help="Отступ при форматировании блоков"
)

opt_allowed_gens = Arg(
    "-g", "--allowed-gens", type=valid_string_list,
    help="Список классов генераторов через запятую, которые нужно запустить"
)

opt_excluded_gens = Arg(
    "-G", "--excluded-gens", type=valid_string_list,
    help="Список классов генераторов через запятую, запуск которых следует исключить"
)

opt_force_enabled = Arg(
    "--force-enabled", type=valid_string_list,
    help="Список классов генераторов через запятую, которые не нужно считать DISABLED даже при наличии тега"
)

opt_generators_context = Arg(
    "--generators_context", type=str, default=None,
    help=argparse.SUPPRESS
)

opt_no_acl = Arg(
    "--no-acl", default=False,
    help="Отключение ACL при генерации"
)

opt_no_acl_exclusive = Arg(
    "--no-acl-exclusive", default=False,
    help="Проверяем что ACL выполненных генераторов не пересекаются"
)

opt_acl_safe = Arg(
    "--acl-safe", default=False,
    help="Использовать более строгий safe acl для фильтрации результата генерации"
)

opt_show_rules = Arg(
    "--show-rules", default=False,
    help="Показывать правила rulebook при выводе диффа"
)

opt_tolerate_fails = Arg(
    "--tolerate-fails", default=False,
    help="Рапортовать об ошибках без остановки генерации"
)

# При параллельном запуске и включённом --tolerate-fails код возврата
# всегда нулевой. Это не позволяет нам легко понять, прошла ли генерация
# успешно для всех устройств. С этим флажком код будет ненулевой, если
# генерация упала хотя бы для одного устройства. А в хелпе эту переменную
# не выводим, там и так не протолкнуться от флагов.
opt_strict_exit_code = Arg(
    "--strict-exit-code", default=False,
    help=argparse.SUPPRESS,
)

opt_required_packages_check = Arg(
    "--required-packages-check", default=False,
    help="Включить проверку наличия установленных deb-пакетов для Entire-генераторов"
)

opt_profile = Arg(
    "--profile", default=False,
    help="Показать в stderr время, затраченное на работу генераторов и обращениям к RackTables"
)


opt_parallel = Arg(
    "-P", "--parallel", type=int, default=1,
    help="Количество одновременных потоков генерирования"
)

opt_max_tasks = Arg(
    "--max-tasks", type=int, default=None,
    help="Рестартовать воркеры каждые N устройств, для сброса кеша и ограничения потребления памяти"
         "По умолчанию - не рестартовать"
)

opt_annotate = Arg(
    "--annotate", default=False,
    help="Добавить к сгенерированному конфигу комментарии о том откуда строчка взялась"
)

opt_config = Arg(
    "--config", default="running", type=valid_config_source,
    help="'cfglister', 'running', 'empty', путь к файлу конфига, "
         "каталогу с файлами конфига в формате <hostname>.cfg "
         "или '-' (stdin)"
)

opt_clear = Arg(
    "--clear", default=False,
    help="Используя acl вычищает команды относящиеся к данному генератору"
         "аналогично использованию return в самом начале генератора"
)

opt_filter_acl = Arg(
    "--filter-acl", default="",
    help="путь к файлу с дополнительным фильтрующим acl, или '-' (stdin)"
)

opt_filter_ifaces = Arg(
    "-i", "--filter-ifaces", default=[], type=valid_string_list,
    help="Генерирует filter-acl по имени интерфейса. "
         "Принимает регекспы, через запятую: '-i 10GE,100GE'. "
         "По-умолчанию добавляет '.*' к концу каждого. "
         "Для указания имени точно, следует добавлять '$': '-i ae0$'. "
         "Если filter-acl передан напрямую, данная опция игнорируется."
)

opt_filter_peers = Arg(
    "-fp", "--filter-peers", default=[], type=valid_string_list,
    help="Генерирует filter-acl по адресу/имени группы/дескрипшену пира."
)

opt_filter_policies = Arg(
    "-frp", "--filter-policies", default=[], type=valid_string_list,
    help="Генерирует filter-acl по названию политик, название должно строго соответствовать, частичные имена не пройдут"
)

opt_ask_pass = Arg(
    "--ask-pass", default=False,
    help="Спросить пароль на подключение"
)

opt_no_ask_deploy = Arg(
    "--no-ask-deploy", default=False,
    help="Не подтвеждать команды перед выполнением"
)

opt_no_progress = Arg(
    "--no-progress", default=False,
    help="Выключить графику прогресс баров комокутора"
)

opt_log_json = Arg(
    "--log-json", default=False,
    help="Логгировать в формате json (default: plain text)"
)

opt_log_dest = Arg(
    "--log-dest", default="deploy/",
    help="Логгировать в указанный файл/директорию, или в stdout, если указать '-'"
)

opt_log_nogroup = Arg(
    "--log-nogroup", default=False,
    help="Не создавать в директории LOG-DEST поддиректории DATE_TIME/"
)

opt_max_slots = Arg(
    "--max-slots", default=30, type=int,
    help="Количество одновременно обрабатываемых asyncio устройств"
)

opt_hosts_range = Arg(
    "--hosts-range", type=valid_range,
    help="Обработать только указанный диапазон хостов. 10 - первые 10. 10:20 - хосты с 10-го по 20-ый"
)

opt_add_comments = Arg(
    "--add-comments", default=False,
    help="Добавлять комменты подтверждения для rbprocess"
)

opt_no_label = Arg(
    "--no-label", default=False,
    help="Убрать лейбл с именем файла из вывода"
)

opt_no_color = Arg(
    "--no-color", default=False,
    help="Не делать ANSI-раскраску вывода (при --dest включён)"
)

opt_no_check_diff = Arg(
    "--no-check-diff", default=False,
    help="не запрашивать дифф после деплоя"
)

opt_dont_commit = Arg(
    "--dont-commit", default=False,
    help="не добавлять команду commit во время деплоя"
)

opt_rollback = Arg(
    "--rollback", default=False,
    help="предложить откат после деплоя где это возможно"
)

opt_fail_on_empty_config = Arg(
    "--fail-on-empty-config", default=False,
    help=argparse.SUPPRESS,
)


opt_show_generators_format = Arg(
    "--format", default="text", choices=["text", "json"],
    help="Формат выдачи"
)


class EntireReloadFlag(enum.Enum):
    no = "no"
    yes = "yes"
    force = "force"

    def __bool__(self):
        return self is not self.no

    def __str__(self):
        return str(self.value)

    __repr__ = __str__


opt_entire_reload = Arg(
    "--entire-reload",
    type=EntireReloadFlag,
    default=EntireReloadFlag.yes,
    choices=list(EntireReloadFlag),
    const=EntireReloadFlag.yes,
    nargs="?",
    help="Выполнить reload() при deploy'e entire генераторов. "
    "no/yes/force - нет/только если файл изменился/даже если не изменился"
)

opt_show_hosts_progress = Arg(
    "--show-hosts-progress", default=False,
    help="Показывать проценты выполнения по хостам"
)

opt_no_collapse = Arg(
    "--no-collapse", default=False,
    help="Не схлопывать одинаковые diff для группы устройств (при --dest включён)"
)

opt_fails_only = Arg(
    "--fails-only", default=False,
    help="Показать только устройства с ошибками"
)

opt_connect_timeout = Arg(
    "--connect-timeout", default=DefaultFromEnv("ANN_CONNECT_TIMEOUT", "20.0"), type=float,
    help="Таймаут на подключение к устройству в секундах."
         " Значение по-умолчанию можно задать в переменной окружения ANN_CONNECT_TIMEOUT"
)

opt_selected_context_name = Arg(
    "context-name", type=str, help="Имя контекста в файле конфигурации"
)


# ====
class CacheOptions(ArgGroup):
    no_mesh = False


class QueryOptionsBase(CacheOptions):
    @property
    @abc.abstractmethod
    def query(self) -> "Query":
        pass

    @property
    @abc.abstractmethod
    def hosts_range(self):
        pass

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not isinstance(self.query, Query):
            query_type = storage_connector.get().query()
            self.query = query_type.new(self.query, hosts_range=self.hosts_range)

    def validate_stdin(self, arg, val, **kwargs):
        if "storage" in kwargs and arg == "config":
            storage = kwargs["storage"]
            if len(storage.resolve_object_ids_by_query(self.query)) > 1:
                raise ValueError("stdin config can not be used with multiple devices")
        super().validate_stdin(arg, val, **kwargs)


class QueryOptions(QueryOptionsBase):
    query = opt_query
    hosts_range = opt_hosts_range


class QueryOptionsOptional(QueryOptionsBase):
    query = opt_query_optional
    hosts_range = opt_hosts_range


class ParallelOptions(ArgGroup):
    parallel = opt_parallel
    max_tasks = opt_max_tasks


class GenSelectOptions(ArgGroup):
    allowed_gens = opt_allowed_gens
    excluded_gens = opt_excluded_gens
    force_enabled = opt_force_enabled
    generators_context = opt_generators_context
    ignore_disabled = False


class GenOptions(QueryOptions, GenSelectOptions, CacheOptions, ParallelOptions):
    no_acl = opt_no_acl
    no_acl_exclusive = opt_no_acl_exclusive
    acl_safe = opt_acl_safe
    filter_acl = opt_filter_acl
    filter_ifaces = opt_filter_ifaces
    filter_peers = opt_filter_peers
    filter_policies = opt_filter_policies
    profile = opt_profile
    tolerate_fails = opt_tolerate_fails
    required_packages_check = opt_required_packages_check
    strict_exit_code = opt_strict_exit_code
    fail_on_empty_config = opt_fail_on_empty_config


class ComocutorOptions(ArgGroup):
    ask_pass = opt_ask_pass
    max_slots = opt_max_slots
    no_progress = opt_no_progress
    connect_timeout = opt_connect_timeout


class CliLoggingOptions(ArgGroup):
    log_json = opt_log_json
    log_dest = opt_log_dest
    log_nogroup = opt_log_nogroup


class DeviceCliOptions(ComocutorOptions, CliLoggingOptions):
    no_ask_deploy = opt_no_ask_deploy
    dont_commit = opt_dont_commit


class FileOutOptions(ArgGroup):
    dest = opt_dest
    expand_path = opt_expand_path
    no_label = opt_no_label
    no_color = opt_no_color

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.dest:
            self.no_color = True


class DiffOptions(GenOptions, ComocutorOptions):
    clear = opt_clear
    config = opt_config


class FileInputOptions(ArgGroup):
    old = opt_old
    new = opt_new
    hw = opt_hw
    fails_only = opt_fails_only


class PatchOptions(DiffOptions):
    add_comments = opt_add_comments


class DeployOptions(PatchOptions, DeviceCliOptions):
    no_check_diff = opt_no_check_diff
    entire_reload = opt_entire_reload
    rollback = opt_rollback


class ShowGenOptions(GenOptions, FileOutOptions):
    indent = opt_indent
    annotate = opt_annotate
    show_hosts_progress = opt_show_hosts_progress


class ShowDiffOptions(DiffOptions, FileOutOptions):
    indent = opt_indent
    show_rules = opt_show_rules
    no_collapse = opt_no_collapse

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.dest:
            self.no_collapse = True


class ShowPatchOptions(PatchOptions, FileOutOptions):
    indent = opt_indent
    show_hosts_progress = opt_show_hosts_progress


class FileDiffOptions(FileInputOptions, FileOutOptions, ParallelOptions):
    indent = opt_indent
    show_rules = opt_show_rules


class FilePatchOptions(FileInputOptions, FileOutOptions, ParallelOptions):
    indent = opt_indent
    add_comments = opt_add_comments


class ShowGeneratorsOptions(QueryOptionsOptional, GenSelectOptions):
    format = opt_show_generators_format
    acl_safe = opt_acl_safe
    ignore_disabled = False


class SelectContext(ArgGroup):
    context_name = opt_selected_context_name
