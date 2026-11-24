"""Генерирует XML-метаданные расширения АнализЗапасов (отчёт «Залежавшиеся товары»).
BSL-модули пишутся вручную; скрипт только добавляет BOM. UUID стабильны (uuid5).
    python -I tools/gen_ext_az.py
"""
import sys
import uuid
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
EXT = "АнализЗапасов"
ROOT = Path(__file__).resolve().parents[1] / "src" / "ext" / EXT
NS = uuid.UUID("6f1c2d3e-0000-4000-8000-0000000a2a01")
U = lambda key: str(uuid.uuid5(NS, key))

REP = "аз_ЗалежавшиесяТовары"
CM = "аз_ЗалежавшиесяТоварыСервер"
ROLE = "аз_ОсновнаяРоль"
SUB, SUB_UUID = "Склад", "8eebe9bd-1a1f-4ce7-aa4a-d0bf6da0ef81"
LANG_UUID = "db4a9ccb-9ef5-4b3c-8577-b6fe5db1b62e"

NSATTR = ('xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:app="http://v8.1c.ru/8.2/managed-application/core" '
          'xmlns:cfg="http://v8.1c.ru/8.1/data/enterprise/current-config" xmlns:cmi="http://v8.1c.ru/8.2/managed-application/cmi" '
          'xmlns:ent="http://v8.1c.ru/8.1/data/enterprise" xmlns:lf="http://v8.1c.ru/8.2/managed-application/logform" '
          'xmlns:style="http://v8.1c.ru/8.1/data/ui/style" xmlns:sys="http://v8.1c.ru/8.1/data/ui/fonts/system" '
          'xmlns:v8="http://v8.1c.ru/8.1/data/core" xmlns:v8ui="http://v8.1c.ru/8.1/data/ui" xmlns:web="http://v8.1c.ru/8.1/data/ui/colors/web" '
          'xmlns:win="http://v8.1c.ru/8.1/data/ui/colors/windows" xmlns:xen="http://v8.1c.ru/8.3/xcf/enums" '
          'xmlns:xpr="http://v8.1c.ru/8.3/xcf/predef" xmlns:xr="http://v8.1c.ru/8.3/xcf/readable" '
          'xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="2.20"')
HDR = f'<?xml version="1.0" encoding="UTF-8"?>\n<MetaDataObject {NSATTR}>\n'


def ru(text, tag):
    return f"<{tag}><v8:item><v8:lang>ru</v8:lang><v8:content>{text}</v8:content></v8:item></{tag}>"


def write(rel, text, bom=False):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8-sig" if bom else "utf-8")
    print("  ", rel)


# ---------- Configuration.xml ----------
CLASSES = ["9cd510cd-abfc-11d4-9434-004095e12fc7", "9fcd25a0-4822-11d4-9414-008048da11f9", "e3687481-0a87-462c-a166-9f34594f9bba",
           "9de14907-ec23-4a07-96f0-85521cb6b53b", "51f2d5d8-ea4d-4064-8892-82951750031e", "e68182ea-4237-4383-967f-90c1e3370bc7",
           "fb282519-d103-4dd3-bc12-cb271d631dfc"]
contained = "".join(f"<xr:ContainedObject><xr:ClassId>{c}</xr:ClassId><xr:ObjectId>{U('cfg' + c)}</xr:ObjectId></xr:ContainedObject>" for c in CLASSES)
write("Configuration.xml", HDR + f"""<Configuration uuid="{U('Configuration')}"><InternalInfo>{contained}</InternalInfo>
<Properties><ObjectBelonging>Adopted</ObjectBelonging><Name>{EXT}</Name>{ru("Анализ запасов", "Synonym")}<Comment/>
<ConfigurationExtensionPurpose>AddOn</ConfigurationExtensionPurpose><KeepMappingToExtendedConfigurationObjectsByIDs>true</KeepMappingToExtendedConfigurationObjectsByIDs>
<NamePrefix>аз_</NamePrefix><ConfigurationExtensionCompatibilityMode>Version8_3_24</ConfigurationExtensionCompatibilityMode>
<DefaultRunMode>ManagedApplication</DefaultRunMode><UsePurposes><v8:Value xsi:type="app:ApplicationUsePurpose">PlatformApplication</v8:Value></UsePurposes>
<ScriptVariant>Russian</ScriptVariant><DefaultRoles><xr:Item xsi:type="xr:MDObjectRef">Role.{ROLE}</xr:Item></DefaultRoles>
<Vendor/><Version>1.0.0.1</Version><DefaultLanguage>Language.Русский</DefaultLanguage><BriefInformation/><DetailedInformation/><Copyright/>
<VendorInformationAddress/><ConfigurationInformationAddress/><InterfaceCompatibilityMode>TaxiEnableVersion8_2</InterfaceCompatibilityMode></Properties>
<ChildObjects><Language>Русский</Language><Subsystem>{SUB}</Subsystem><Role>{ROLE}</Role><CommonModule>{CM}</CommonModule><Report>{REP}</Report></ChildObjects>
</Configuration></MetaDataObject>""")

write("Languages/Русский.xml", HDR + f"""<Language uuid="{U('Русский')}"><InternalInfo/><Properties><ObjectBelonging>Adopted</ObjectBelonging><Name>Русский</Name><Comment/>
<ExtendedConfigurationObject>{LANG_UUID}</ExtendedConfigurationObject><LanguageCode>ru</LanguageCode></Properties></Language></MetaDataObject>""")

# ---------- общий модуль ----------
write(f"CommonModules/{CM}.xml", HDR + f"""<CommonModule uuid="{U(CM)}"><Properties><Name>{CM}</Name>{ru("Залежавшиеся товары (сервер)", "Synonym")}<Comment/>
<Global>false</Global><ClientManagedApplication>false</ClientManagedApplication><Server>true</Server><ExternalConnection>true</ExternalConnection>
<ClientOrdinaryApplication>false</ClientOrdinaryApplication><ServerCall>false</ServerCall><Privileged>false</Privileged><ReturnValuesReuse>DontUse</ReturnValuesReuse>
</Properties></CommonModule></MetaDataObject>""")

# ---------- отчёт ----------
gen = "".join(f'<xr:GeneratedType name="{p}.{REP}" category="{c}"><xr:TypeId>{U(p + "t")}</xr:TypeId><xr:ValueId>{U(p + "v")}</xr:ValueId></xr:GeneratedType>'
              for p, c in (("ReportObject", "Object"), ("ReportManager", "Manager")))
write(f"Reports/{REP}.xml", HDR + f"""<Report uuid="{U(REP)}"><InternalInfo>{gen}</InternalInfo><Properties><Name>{REP}</Name>{ru("Залежавшиеся товары", "Synonym")}<Comment/>
<UseStandardCommands>true</UseStandardCommands><DefaultForm>Report.{REP}.Form.ФормаОтчета</DefaultForm><AuxiliaryForm/><MainDataCompositionSchema/>
<DefaultSettingsForm/><AuxiliarySettingsForm/><DefaultVariantForm/><VariantsStorage/><SettingsStorage/><IncludeHelpInContents>false</IncludeHelpInContents>
<ExtendedPresentation/>{ru("Товары на остатке, которые долго не продаются: сколько дней лежат без продаж и сколько денег в них заморожено", "Explanation")}</Properties>
<ChildObjects><Form>ФормаОтчета</Form></ChildObjects></Report></MetaDataObject>""")

write(f"Reports/{REP}/Forms/ФормаОтчета.xml", HDR + f"""<Form uuid="{U(REP + 'Форма')}"><Properties><Name>ФормаОтчета</Name>{ru("Форма отчета", "Synonym")}<Comment/>
<FormType>Managed</FormType><IncludeHelpInContents>false</IncludeHelpInContents>
<UsePurposes><v8:Value xsi:type="app:ApplicationUsePurpose">PlatformApplication</v8:Value></UsePurposes><ExtendedPresentation/></Properties></Form></MetaDataObject>""")

# ---------- форма ----------
_id = [0]


def nid():
    _id[0] += 1
    return _id[0]


def extras(name):
    return f'<ContextMenu name="{name}КонтекстноеМеню" id="{nid()}"/><ExtendedTooltip name="{name}РасширеннаяПодсказка" id="{nid()}"/>'


def input_field(name, title, width=None, list_choice=False, tooltip=None):
    s = f'<InputField name="{name}" id="{nid()}"><DataPath>{name}</DataPath>{ru(title, "Title")}'
    if tooltip:
        s += ru(tooltip, "ToolTip")
    if width:
        s += f"<Width>{width}</Width><HorizontalStretch>false</HorizontalStretch>"
    if list_choice:
        s += "<ListChoiceMode>true</ListChoiceMode>"
    return s + extras(name) + "</InputField>"


def check_field(name, title):
    return (f'<CheckBoxField name="{name}" id="{nid()}"><DataPath>{name}</DataPath>{ru(title, "Title")}<TitleLocation>Right</TitleLocation>'
            f"<CheckBoxType>Auto</CheckBoxType>{extras(name)}</CheckBoxField>")


def group(name, children):
    return (f'<UsualGroup name="{name}" id="{nid()}"><Group>AlwaysHorizontal</Group><Representation>None</Representation><ShowTitle>false</ShowTitle>'
            f'<ExtendedTooltip name="{name}РасширеннаяПодсказка" id="{nid()}"/><ChildItems>' + "".join(children) + "</ChildItems></UsualGroup>")


T_STR = "<Type><v8:Type>xs:string</v8:Type><v8:StringQualifiers><v8:Length>20</v8:Length><v8:AllowedLength>Variable</v8:AllowedLength></v8:StringQualifiers></Type>"
T_BOOL = "<Type><v8:Type>xs:boolean</v8:Type></Type>"
T_DATE = "<Type><v8:Type>xs:dateTime</v8:Type><v8:DateQualifiers><v8:DateFractions>Date</v8:DateFractions></v8:DateQualifiers></Type>"
T_NUM = "<Type><v8:Type>xs:decimal</v8:Type><v8:NumberQualifiers><v8:Digits>5</v8:Digits><v8:FractionDigits>0</v8:FractionDigits><v8:AllowedSign>Nonnegative</v8:AllowedSign></v8:NumberQualifiers></Type>"
T_ORG = "<Type><v8:Type>cfg:CatalogRef.Организации</v8:Type></Type>"
T_NOM = "<Type><v8:Type>cfg:CatalogRef.Номенклатура</v8:Type></Type>"
T_MXL = '<Type><v8:Type xmlns:mxl="http://v8.1c.ru/8.2/data/spreadsheet">mxl:SpreadsheetDocument</v8:Type></Type>'

body = [
    group("ГруппаПараметры1", [
        input_field("Дата", "На дату", width=10),
        input_field("Организация", "Организация", tooltip="Пусто — все организации"),
        input_field("ГруппаНоменклатуры", "Группа номенклатуры", tooltip="Пусто — вся номенклатура"),
    ]),
    group("ГруппаПараметры2", [
        input_field("ПорогДней", "Без продаж от, дней", width=5, tooltip="В список попадают товары, которые не продавались столько дней или дольше"),
        input_field("Сортировка", "Сортировка", width=18, list_choice=True),
        check_field("ПоказыватьОтрицательные", "Показывать отрицательные остатки"),
    ]),
    f'<SpreadSheetDocumentField name="Результат" id="{nid()}"><DataPath>Результат</DataPath><TitleLocation>None</TitleLocation>'
    f'<VerticalScrollBar>true</VerticalScrollBar><HorizontalScrollBar>true</HorizontalScrollBar>'
    f'<ContextMenu name="РезультатКонтекстноеМеню" id="{nid()}"/><ExtendedTooltip name="РезультатРасширеннаяПодсказка" id="{nid()}"/></SpreadSheetDocumentField>',
]

attrs = []
for i, (name, title, typ, save) in enumerate([
    ("Результат", "Результат", T_MXL, False), ("Дата", "На дату", T_DATE, False), ("Организация", "Организация", T_ORG, True),
    ("ГруппаНоменклатуры", "Группа номенклатуры", T_NOM, True), ("ПорогДней", "Без продаж от, дней", T_NUM, True),
    ("Сортировка", "Сортировка", T_STR, True), ("ПоказыватьОтрицательные", "Показывать отрицательные остатки", T_BOOL, True),
]):
    attrs.append(f'<Attribute name="{name}" id="{i + 1}">{ru(title, "Title")}{typ}' + ("<SavedData>true</SavedData>" if save else "") + "</Attribute>")

cmdbar = (f'<AutoCommandBar name="ФормаКоманднаяПанель" id="-1"><ChildItems><Button name="ФормаСформировать" id="{nid()}"><Type>CommandBarButton</Type>'
          f'<DefaultButton>true</DefaultButton><CommandName>Form.Command.Сформировать</CommandName>'
          f'<ExtendedTooltip name="ФормаСформироватьРасширеннаяПодсказка" id="{nid()}"/></Button></ChildItems></AutoCommandBar>')
cmds = (f'<Commands><Command name="Сформировать" id="1">{ru("Сформировать", "Title")}{ru("Сформировать отчёт", "ToolTip")}'
        f'<Shortcut>Ctrl+Enter</Shortcut><Action>Сформировать</Action></Command></Commands>')

FORM_NS = ('xmlns="http://v8.1c.ru/8.3/xcf/logform" xmlns:app="http://v8.1c.ru/8.2/managed-application/core" '
           'xmlns:cfg="http://v8.1c.ru/8.1/data/enterprise/current-config" xmlns:dcscor="http://v8.1c.ru/8.1/data-composition-system/core" '
           'xmlns:dcssch="http://v8.1c.ru/8.1/data-composition-system/schema" xmlns:dcsset="http://v8.1c.ru/8.1/data-composition-system/settings" '
           'xmlns:ent="http://v8.1c.ru/8.1/data/enterprise" xmlns:lf="http://v8.1c.ru/8.2/managed-application/logform" '
           'xmlns:style="http://v8.1c.ru/8.1/data/ui/style" xmlns:sys="http://v8.1c.ru/8.1/data/ui/fonts/system" xmlns:v8="http://v8.1c.ru/8.1/data/core" '
           'xmlns:v8ui="http://v8.1c.ru/8.1/data/ui" xmlns:web="http://v8.1c.ru/8.1/data/ui/colors/web" xmlns:win="http://v8.1c.ru/8.1/data/ui/colors/windows" '
           'xmlns:xr="http://v8.1c.ru/8.3/xcf/readable" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="2.20"')
form = (f'<?xml version="1.0" encoding="UTF-8"?>\n<Form {FORM_NS}>' + ru("Залежавшиеся товары", "Title")
        + "<AutoTitle>false</AutoTitle><AutoSaveDataInSettings>Use</AutoSaveDataInSettings>" + cmdbar
        + '<Events><Event name="OnCreateAtServer">ПриСозданииНаСервере</Event></Events>'
        + "<ChildItems>" + "".join(body) + "</ChildItems><Attributes>" + "".join(attrs) + "</Attributes>" + cmds + "</Form>")
write(f"Reports/{REP}/Forms/ФормаОтчета/Ext/Form.xml", form)

# ---------- заимствованная подсистема «Склад»: отчёт появится в Склад → Отчеты ----------
write(f"Subsystems/{SUB}.xml", HDR + f"""<Subsystem uuid="{U(SUB)}"><Properties><ObjectBelonging>Adopted</ObjectBelonging><Name>{SUB}</Name><Comment/>
<ExtendedConfigurationObject>{SUB_UUID}</ExtendedConfigurationObject>
<Content><xr:Item xsi:type="xr:MDObjectRef">Report.{REP}</xr:Item></Content></Properties><ChildObjects/></Subsystem></MetaDataObject>""")

# ---------- роль ----------
write(f"Roles/{ROLE}.xml", HDR + f"""<Role uuid="{U(ROLE)}"><Properties><Name>{ROLE}</Name>{ru("Анализ запасов: основная роль", "Synonym")}<Comment/></Properties></Role></MetaDataObject>""", bom=True)
write(f"Roles/{ROLE}/Ext/Rights.xml", f"""<?xml version="1.0" encoding="UTF-8"?>
<Rights xmlns="http://v8.1c.ru/8.2/roles" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="Rights" version="2.20">
	<setForNewObjects>false</setForNewObjects>
	<setForAttributesByDefault>true</setForAttributesByDefault>
	<independentRightsOfChildObjects>false</independentRightsOfChildObjects>
	<object>
		<name>Report.{REP}</name>
		<right><name>Use</name><value>true</value></right>
		<right><name>View</name><value>true</value></right>
	</object>
</Rights>
""", bom=True)

for bsl in ROOT.rglob("*.bsl"):
    raw = bsl.read_bytes()
    if not raw.startswith(b"\xef\xbb\xbf"):
        bsl.write_bytes(b"\xef\xbb\xbf" + raw)
print("ok, form items:", _id[0])
