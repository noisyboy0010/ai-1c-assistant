"""Генерирует XML-метаданные расширения ЗагрузкаИзExcel (обработка, форма, модуль, команда, права).
BSL-модули пишутся вручную; скрипт только добавляет BOM. UUID стабильны (uuid5), повторный запуск ничего не ломает.
"""
import re
import sys
import uuid
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1] / "src" / "ext" / "ЗагрузкаИзExcel"
NS = uuid.UUID("6f1c2d3e-0000-4000-8000-00000000e1c1")
U = lambda key: str(uuid.uuid5(NS, key))

DP = "зиэ_ЗагрузкаСчетовПокупателям"
CM = "зиэ_ЗагрузкаСчетовСервер"
DOC = "СчетНаОплатуПокупателю"
DOC_UUID = "0ff61b1f-319d-49ab-b803-5631722395e9"  # Документ.СчетНаОплатуПокупателю в основной конфигурации
CMD = "зиэ_ЗагрузитьИзExcel"

HDR = ('<?xml version="1.0" encoding="UTF-8"?>\n<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" '
       'xmlns:app="http://v8.1c.ru/8.2/managed-application/core" xmlns:cfg="http://v8.1c.ru/8.1/data/enterprise/current-config" '
       'xmlns:cmi="http://v8.1c.ru/8.2/managed-application/cmi" xmlns:ent="http://v8.1c.ru/8.1/data/enterprise" '
       'xmlns:lf="http://v8.1c.ru/8.2/managed-application/logform" xmlns:style="http://v8.1c.ru/8.1/data/ui/style" '
       'xmlns:sys="http://v8.1c.ru/8.1/data/ui/fonts/system" xmlns:v8="http://v8.1c.ru/8.1/data/core" '
       'xmlns:v8ui="http://v8.1c.ru/8.1/data/ui" xmlns:web="http://v8.1c.ru/8.1/data/ui/colors/web" '
       'xmlns:win="http://v8.1c.ru/8.1/data/ui/colors/windows" xmlns:xen="http://v8.1c.ru/8.3/xcf/enums" '
       'xmlns:xpr="http://v8.1c.ru/8.3/xcf/predef" xmlns:xr="http://v8.1c.ru/8.3/xcf/readable" '
       'xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="2.20">\n')


def ru(text, tag):
    return f"<{tag}><v8:item><v8:lang>ru</v8:lang><v8:content>{text}</v8:content></v8:item></{tag}>"


def write(rel, text, bom=False):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8-sig" if bom else "utf-8")
    print("  ", rel)


def gentypes(kind, name, cats):
    out = []
    for prefix, cat in cats:
        out.append(f'<xr:GeneratedType name="{prefix}.{name}" category="{cat}">'
                   f'<xr:TypeId>{U(prefix + name + "t")}</xr:TypeId><xr:ValueId>{U(prefix + name + "v")}</xr:ValueId></xr:GeneratedType>')
    return "<InternalInfo>" + "".join(out) + "</InternalInfo>"


# ---------- общий модуль ----------
write(f"CommonModules/{CM}.xml", HDR + f"""<CommonModule uuid="{U(CM)}"><Properties><Name>{CM}</Name>{ru("Загрузка счетов из Excel (сервер)", "Synonym")}<Comment/>
<Global>false</Global><ClientManagedApplication>false</ClientManagedApplication><Server>true</Server><ExternalConnection>true</ExternalConnection>
<ClientOrdinaryApplication>false</ClientOrdinaryApplication><ServerCall>false</ServerCall><Privileged>false</Privileged><ReturnValuesReuse>DontUse</ReturnValuesReuse>
</Properties></CommonModule></MetaDataObject>""")

# ---------- обработка ----------
write(f"DataProcessors/{DP}.xml", HDR + f"""<DataProcessor uuid="{U(DP)}">{gentypes("DataProcessor", DP, [("DataProcessorObject", "Object"), ("DataProcessorManager", "Manager")])}
<Properties><Name>{DP}</Name>{ru("Загрузка счетов покупателям из Excel", "Synonym")}<Comment/><UseStandardCommands>true</UseStandardCommands>
<DefaultForm>DataProcessor.{DP}.Form.Форма</DefaultForm><AuxiliaryForm/><IncludeHelpInContents>false</IncludeHelpInContents><ExtendedPresentation/><Explanation/></Properties>
<ChildObjects><Form>Форма</Form></ChildObjects></DataProcessor></MetaDataObject>""")

write(f"DataProcessors/{DP}/Forms/Форма.xml", HDR + f"""<Form uuid="{U(DP + 'Форма')}"><Properties><Name>Форма</Name>{ru("Форма", "Synonym")}<Comment/>
<FormType>Managed</FormType><IncludeHelpInContents>false</IncludeHelpInContents>
<UsePurposes><v8:Value xsi:type="app:ApplicationUsePurpose">PlatformApplication</v8:Value></UsePurposes><ExtendedPresentation/></Properties></Form></MetaDataObject>""")

# ---------- форма ----------
_id = [0]


def nid():
    _id[0] += 1
    return _id[0]


def extras(name):
    return f'<ContextMenu name="{name}КонтекстноеМеню" id="{nid()}"/><ExtendedTooltip name="{name}РасширеннаяПодсказка" id="{nid()}"/>'


def events(ev):
    if not ev:
        return ""
    return "<Events>" + "".join(f'<Event name="{k}">{v}</Event>' for k, v in ev.items()) + "</Events>"


def input_field(name, path, title=None, ro=False, choice_btn=False, list_choice=False, text_edit=True, ev=None, title_loc=None, width=None):
    s = f'<InputField name="{name}" id="{nid()}"><DataPath>{path}</DataPath>'
    if title:
        s += ru(title, "Title")
    if title_loc:
        s += f"<TitleLocation>{title_loc}</TitleLocation>"
    if width:
        s += f"<Width>{width}</Width>"
    if ro:
        s += "<ReadOnly>true</ReadOnly>"
    if choice_btn:
        s += "<ChoiceButton>true</ChoiceButton>"
    if list_choice:
        s += "<ListChoiceMode>true</ListChoiceMode>"
    if not text_edit:
        s += "<TextEdit>false</TextEdit>"
    return s + extras(name) + events(ev) + "</InputField>"


def check_field(name, path, title=None, ro=False, title_loc=None, ev=None):
    s = f'<CheckBoxField name="{name}" id="{nid()}"><DataPath>{path}</DataPath>'
    if title:
        s += ru(title, "Title")
    if title_loc:
        s += f"<TitleLocation>{title_loc}</TitleLocation>"
    if ro:
        s += "<ReadOnly>true</ReadOnly>"
    return s + "<CheckBoxType>Auto</CheckBoxType>" + extras(name) + events(ev) + "</CheckBoxField>"


def group(name, children, title=None, horizontal=False):
    s = f'<UsualGroup name="{name}" id="{nid()}">'
    if title:
        s += ru(title, "Title")
    s += f"<Group>{'AlwaysHorizontal' if horizontal else 'Vertical'}</Group>"
    s += "<Representation>" + ("NormalSeparation" if title else "None") + "</Representation>"
    s += f"<ShowTitle>{'true' if title else 'false'}</ShowTitle>"
    s += f'<ExtendedTooltip name="{name}РасширеннаяПодсказка" id="{nid()}"/><ChildItems>' + "".join(children) + "</ChildItems></UsualGroup>"
    return s


def table(name, path, columns, rows=None, change_rowset=False, ev=None):
    s = f'<Table name="{name}" id="{nid()}"><Representation>List</Representation>'
    s += f"<ChangeRowSet>{'true' if change_rowset else 'false'}</ChangeRowSet><ChangeRowOrder>false</ChangeRowOrder>"
    if rows:
        s += f"<HeightInTableRows>{rows}</HeightInTableRows>"
    s += f"<AutoInsertNewRow>false</AutoInsertNewRow><DataPath>{path}</DataPath>"
    s += "<SearchStringLocation>None</SearchStringLocation><ViewStatusLocation>None</ViewStatusLocation><SearchControlLocation>None</SearchControlLocation>"
    s += '<RowFilter xsi:nil="true"/>'
    s += f'<ContextMenu name="{name}КонтекстноеМеню" id="{nid()}"/><AutoCommandBar name="{name}КоманднаяПанель" id="{nid()}"><Autofill>false</Autofill></AutoCommandBar>'
    s += f'<ExtendedTooltip name="{name}РасширеннаяПодсказка" id="{nid()}"/>'
    for add, typ in (("СтрокаПоиска", "SearchStringRepresentation"), ("СостояниеПросмотра", "ViewStatusRepresentation"), ("УправлениеПоиском", "SearchControl")):
        tag = {"SearchStringRepresentation": "SearchStringAddition", "ViewStatusRepresentation": "ViewStatusAddition", "SearchControl": "SearchControlAddition"}[typ]
        s += (f'<{tag} name="{name}{add}" id="{nid()}"><AdditionSource><Item>{name}</Item><Type>{typ}</Type></AdditionSource>'
              f'<ContextMenu name="{name}{add}КонтекстноеМеню" id="{nid()}"/><ExtendedTooltip name="{name}{add}РасширеннаяПодсказка" id="{nid()}"/></{tag}>')
    s += events(ev)
    return s + "<ChildItems>" + "".join(columns) + "</ChildItems></Table>"


def button(name, cmd, default=False):
    s = f'<Button name="{name}" id="{nid()}"><Type>CommandBarButton</Type>'
    if default:
        s += "<DefaultButton>true</DefaultButton>"
    return s + f'<CommandName>Form.Command.{cmd}</CommandName><ExtendedTooltip name="{name}РасширеннаяПодсказка" id="{nid()}"/></Button>'


T_STR = "<Type><v8:Type>xs:string</v8:Type><v8:StringQualifiers><v8:Length>0</v8:Length><v8:AllowedLength>Variable</v8:AllowedLength></v8:StringQualifiers></Type>"
T_BOOL = "<Type><v8:Type>xs:boolean</v8:Type></Type>"
T_DATE = "<Type><v8:Type>xs:dateTime</v8:Type><v8:DateQualifiers><v8:DateFractions>Date</v8:DateFractions></v8:DateQualifiers></Type>"
T_ANY = "<Type/>"


def T_NUM(d, f):
    return (f"<Type><v8:Type>xs:decimal</v8:Type><v8:NumberQualifiers><v8:Digits>{d}</v8:Digits>"
            f"<v8:FractionDigits>{f}</v8:FractionDigits><v8:AllowedSign>Any</v8:AllowedSign></v8:NumberQualifiers></Type>")


attr_id = [0]


def attribute(name, title, typ, columns=None):
    attr_id[0] += 1
    s = f'<Attribute name="{name}" id="{attr_id[0]}">{ru(title, "Title")}{typ}'
    if columns:
        s += "<Columns>" + "".join(f'<Column name="{c}" id="{i + 1}">{ru(t, "Title")}{ty}</Column>' for i, (c, t, ty) in enumerate(columns)) + "</Columns>"
    return s + "</Attribute>"


ROWS_COLS = [
    ("Загружать", "Загружать", T_BOOL), ("НомерСтрокиФайла", "Строка", T_NUM(10, 0)), ("КлючСчета", "Ключ счёта", T_STR),
    ("НомерСчета", "№ счёта", T_STR), ("Дата", "Дата", T_DATE), ("ИНН", "ИНН", T_STR), ("Покупатель", "Покупатель", T_STR),
    ("Артикул", "Артикул", T_STR), ("Номенклатура", "Товар / услуга", T_STR), ("ЕдиницаИзмерения", "Ед.", T_STR),
    ("Количество", "Кол-во", T_NUM(15, 3)), ("Цена", "Цена", T_NUM(15, 2)), ("Сумма", "Сумма", T_NUM(15, 2)),
    ("СтавкаНДС", "НДС", T_STR), ("Комментарий", "Комментарий", T_STR), ("Статус", "Статус", T_STR), ("Ошибка", "Ошибка", T_BOOL),
]

body = []
body.append(group("ГруппаФайл", [
    input_field("ИмяФайла", "ИмяФайла", "Файл Excel", choice_btn=True, text_edit=False, ev={"StartChoice": "ИмяФайлаНачалоВыбора"}),
    input_field("СтрокаЗаголовка", "СтрокаЗаголовка", "Строка заголовков", width=4, ev={"OnChange": "СтрокаЗаголовкаПриИзменении"}),
], horizontal=True))
body.append(group("ГруппаПараметры", [
    input_field("Организация", "Организация", "Организация", list_choice=True, ev={"OnChange": "ОрганизацияПриИзменении"}),
    check_field("НоваяНоменклатураУслуга", "НоваяНоменклатураУслуга", "Новая номенклатура - услуги"),
    check_field("Проводить", "Проводить", "Проводить счета"),
], horizontal=True))
body.append(group("ГруппаСопоставление", [table("Сопоставление", "Сопоставление", [
    input_field("СопоставлениеПредставление", "Сопоставление.Представление", "Поле счёта", ro=True),
    input_field("СопоставлениеКолонка", "Сопоставление.Колонка", "Колонка файла", list_choice=True, ev={"OnChange": "СопоставлениеКолонкаПриИзменении"}),
    check_field("СопоставлениеОбязательное", "Сопоставление.Обязательное", "Обязательное", ro=True),
], rows=6)], title="Сопоставление колонок"))
body.append(f'<LabelField name="ИтогИнфо" id="{nid()}"><DataPath>ИтогИнфо</DataPath><TitleLocation>None</TitleLocation>'
            f'<ContextMenu name="ИтогИнфоКонтекстноеМеню" id="{nid()}"/><ExtendedTooltip name="ИтогИнфоРасширеннаяПодсказка" id="{nid()}"/></LabelField>')
row_cols = [check_field("СтрокиЗагружать", "Строки.Загружать", " ", title_loc="None", ev={"OnChange": "СтрокиЗагружатьПриИзменении"})]
for c, t, _ in ROWS_COLS[1:]:
    if c in ("КлючСчета", "Ошибка", "Артикул"):
        continue
    row_cols.append(input_field("Строки" + c, "Строки." + c, ro=True))
body.append(group("ГруппаСтроки", [table("Строки", "Строки", row_cols, rows=10)], title="Предпросмотр"))
body.append(group("ГруппаСозданные", [table("Созданные", "Созданные", [
    input_field("СозданныеДокумент", "Созданные.Документ", "Созданный счёт", ro=True),
], rows=4, ev={"Selection": "СозданныеВыбор"})], title="Созданные счета"))

cmdbar = f'<AutoCommandBar name="ФормаКоманднаяПанель" id="-1"><ChildItems>{button("ФормаЗагрузить", "Загрузить", True)}{button("ФормаПеречитать", "Перечитать")}</ChildItems></AutoCommandBar>'

attrs = "".join([
    attribute("ИмяФайла", "Файл", T_STR),
    attribute("АдресФайла", "Адрес файла", T_STR),
    attribute("АдресДанных", "Адрес данных", T_STR),
    attribute("СтрокаЗаголовка", "Строка заголовков", T_NUM(5, 0)),
    attribute("Организация", "Организация", T_ANY),
    attribute("Проводить", "Проводить", T_BOOL),
    attribute("НоваяНоменклатураУслуга", "Новая номенклатура - услуги", T_BOOL),
    attribute("ИтогИнфо", "Итог", T_STR),
    attribute("Сопоставление", "Сопоставление", "<Type><v8:Type>v8:ValueTable</v8:Type></Type>",
              [("Поле", "Поле", T_STR), ("Представление", "Поле счёта", T_STR), ("Колонка", "Колонка файла", T_STR), ("Обязательное", "Обязательное", T_BOOL)]),
    attribute("Строки", "Строки", "<Type><v8:Type>v8:ValueTable</v8:Type></Type>", ROWS_COLS),
    attribute("Созданные", "Созданные", "<Type><v8:Type>v8:ValueTable</v8:Type></Type>", [("Документ", "Документ", T_ANY)]),
])

cmds = (f'<Commands><Command name="Загрузить" id="1">{ru("Загрузить счета", "Title")}{ru("Создать счета по отмеченным строкам", "ToolTip")}'
        f'<Action>Загрузить</Action></Command><Command name="Перечитать" id="2">{ru("Перечитать файл", "Title")}<Action>Перечитать</Action></Command></Commands>')

form = ('<?xml version="1.0" encoding="UTF-8"?>\n<Form xmlns="http://v8.1c.ru/8.3/xcf/logform" xmlns:app="http://v8.1c.ru/8.2/managed-application/core" '
        'xmlns:cfg="http://v8.1c.ru/8.1/data/enterprise/current-config" xmlns:dcscor="http://v8.1c.ru/8.1/data-composition-system/core" '
        'xmlns:dcssch="http://v8.1c.ru/8.1/data-composition-system/schema" xmlns:dcsset="http://v8.1c.ru/8.1/data-composition-system/settings" '
        'xmlns:ent="http://v8.1c.ru/8.1/data/enterprise" xmlns:lf="http://v8.1c.ru/8.2/managed-application/logform" '
        'xmlns:style="http://v8.1c.ru/8.1/data/ui/style" xmlns:sys="http://v8.1c.ru/8.1/data/ui/fonts/system" xmlns:v8="http://v8.1c.ru/8.1/data/core" '
        'xmlns:v8ui="http://v8.1c.ru/8.1/data/ui" xmlns:web="http://v8.1c.ru/8.1/data/ui/colors/web" xmlns:win="http://v8.1c.ru/8.1/data/ui/colors/windows" '
        'xmlns:xr="http://v8.1c.ru/8.3/xcf/readable" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="2.20">'
        + ru("Загрузка счетов покупателям из Excel", "Title") + "<AutoTitle>false</AutoTitle>" + cmdbar
        + '<Events><Event name="OnCreateAtServer">ПриСозданииНаСервере</Event></Events>'
        + "<ChildItems>" + "".join(body) + "</ChildItems><Attributes>" + attrs + "</Attributes>" + cmds + "</Form>")
write(f"DataProcessors/{DP}/Forms/Форма/Ext/Form.xml", form)

# ---------- заимствованная подсистема «Продажи»: обработка появится в разделе Продажи → Сервис ----------
# (панель списка счетов в БП собрана вручную, Autofill=false, команды расширений туда не попадают)
SUB = "Продажи"
SUB_UUID = "2885099a-00f4-481b-8469-faee8a208e7c"
write(f"Subsystems/{SUB}.xml", HDR + f"""<Subsystem uuid="{U(SUB)}"><Properties><ObjectBelonging>Adopted</ObjectBelonging><Name>{SUB}</Name><Comment/>
<ExtendedConfigurationObject>{SUB_UUID}</ExtendedConfigurationObject>
<Content><xr:Item xsi:type="xr:MDObjectRef">DataProcessor.{DP}</xr:Item></Content></Properties><ChildObjects/></Subsystem></MetaDataObject>""")

# ---------- права роли ----------
write("Roles/зиэ_ОсновнаяРоль/Ext/Rights.xml", """<?xml version="1.0" encoding="UTF-8"?>
<Rights xmlns="http://v8.1c.ru/8.2/roles" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="Rights" version="2.20">
	<setForNewObjects>false</setForNewObjects>
	<setForAttributesByDefault>true</setForAttributesByDefault>
	<independentRightsOfChildObjects>false</independentRightsOfChildObjects>
	<object>
		<name>DataProcessor.%s</name>
		<right><name>Use</name><value>true</value></right>
		<right><name>View</name><value>true</value></right>
	</object>
</Rights>
""" % (DP,), bom=True)

# ---------- Configuration.xml: состав ----------
cfg = ROOT / "Configuration.xml"
t = cfg.read_text(encoding="utf-8-sig")
children = ("<ChildObjects>\n\t\t\t<Language>Русский</Language>\n\t\t\t<Subsystem>Продажи</Subsystem>\n\t\t\t<Role>зиэ_ОсновнаяРоль</Role>\n"
            f"\t\t\t<CommonModule>{CM}</CommonModule>\n\t\t\t<DataProcessor>{DP}</DataProcessor>\n\t\t</ChildObjects>")
t = re.sub(r"<ChildObjects>.*?</ChildObjects>", children, t, flags=re.S)
cfg.write_text(t, encoding="utf-8")
print("   Configuration.xml")

# ---------- BOM для модулей ----------
for bsl in ROOT.rglob("*.bsl"):
    raw = bsl.read_bytes()
    if not raw.startswith(b"\xef\xbb\xbf"):
        bsl.write_bytes(b"\xef\xbb\xbf" + raw)
print("ok, form items:", _id[0])
