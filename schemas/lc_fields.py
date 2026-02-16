"""
LC Fields Schema — SINGLE SOURCE OF TRUTH.

This module defines every field in the L/C application.
Used by: extraction prompts, frontend form generation, validation rules, export.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FieldDef:
    """Definition of a single form field."""
    key: str
    en: str                                 # English label
    ar: str                                 # Arabic label
    es: str = ""                            # Spanish label
    it: str = ""                            # Italian label
    type: str = "text"                      # text | textarea | date | number | select | checkbox
    options: list[str] = field(default_factory=list)  # For select fields
    section: str = ""                       # Parent section key
    required: bool = False                  # Required for submission
    extractable: bool = True                # Can be extracted from PDF

    def label(self, lang: str = "en") -> str:
        """Get label in the specified language, fallback to English."""
        return getattr(self, lang, "") or self.en


@dataclass
class SectionDef:
    """Definition of a form section."""
    key: str
    en: str
    ar: str
    es: str = ""
    it: str = ""
    fields: list[FieldDef] = field(default_factory=list)

    def label(self, lang: str = "en") -> str:
        return getattr(self, lang, "") or self.en


# ══════════════════════════════════════════════════════════════════════════════
#  FULL LC FIELDS DEFINITION
# ══════════════════════════════════════════════════════════════════════════════

SECTIONS: list[SectionDef] = [
    SectionDef(
        key="basic_information",
        en="Basic Information", ar="المعلومات الأساسية",
        es="Información Básica", it="Informazioni di Base",
        fields=[
            FieldDef("date", "Date", "التاريخ", "Fecha", "Data", type="date"),
            FieldDef("lc_number", "L/C Number", "رقم الإعتماد", "Número L/C", "Numero L/C", required=True),
            FieldDef("branch_reference", "Branch Reference", "إشاري الفرع", "Ref. Sucursal", "Rif. Filiale"),
            FieldDef("branch_code", "Branch Code", "رقم الفرع", "Código Sucursal", "Codice Filiale"),
            FieldDef("year", "Year", "السنة", "Año", "Anno"),
            FieldDef("cbl_key", "CBL KEY", "مفتاح مصرف ليبيا المركزي", "Clave CBL", "Chiave CBL"),
        ],
    ),
    SectionDef(
        key="account_information",
        en="Account Information", ar="معلومات الحساب",
        es="Información de Cuenta", it="Informazioni Conto",
        fields=[
            FieldDef("for_account_of", "For Account of", "لحساب", "A Cuenta de", "Per Conto di"),
            FieldDef("account_number", "Account Number", "رقم الحساب", "Número de Cuenta", "Numero Conto"),
            FieldDef("applicant_name", "Applicant Name", "اسم فاتح الإعتماد", "Nombre del Solicitante", "Nome del Richiedente", required=True),
            FieldDef("applicant_address", "Applicant Address", "عنوان فاتح الإعتماد", "Dirección del Solicitante", "Indirizzo del Richiedente", type="textarea"),
            FieldDef("telephone", "Telephone", "رقم الهاتف", "Teléfono", "Telefono"),
            FieldDef("fax", "Fax", "الفاكس", "Fax", "Fax"),
        ],
    ),
    SectionDef(
        key="beneficiary_information",
        en="Beneficiary Information", ar="معلومات المستفيد",
        es="Información del Beneficiario", it="Informazioni Beneficiario",
        fields=[
            FieldDef("beneficiary_name", "Beneficiary Name and Address", "اسم وعناوين المستفيد", "Nombre y Dirección del Beneficiario", "Nome e Indirizzo Beneficiario", type="textarea", required=True),
            FieldDef("beneficiary_contact", "Beneficiary Contact (Tele-Fax)", "رقم الهاتف والفاكس للمستفيد", "Contacto Beneficiario", "Contatto Beneficiario"),
            FieldDef("beneficiary_bank", "Beneficiary Bank", "مصرف المستفيد بالخارج", "Banco del Beneficiario", "Banca Beneficiario"),
            FieldDef("beneficiary_bank_swift", "Beneficiary Bank SWIFT/BIC", "رمز سويفت/بيك لمصرف المستفيد", "SWIFT/BIC Banco Beneficiario", "SWIFT/BIC Banca Beneficiario"),
            FieldDef("available_at_correspondent", "Available at Correspondent Bank", "متاح لدى مراسلنا الذي", "Disponible en Banco Corresponsal", "Disponibile presso Banca Corrispondente"),
        ],
    ),
    SectionDef(
        key="credit_amount_information",
        en="Credit Amount", ar="قيمة الإعتماد",
        es="Importe del Crédito", it="Importo del Credito",
        fields=[
            FieldDef("amount_in_figures", "Amount in Figures", "قيمة الإعتماد بالأرقام", "Importe en Cifras", "Importo in Cifre", required=True),
            FieldDef("amount_in_letters", "Amount in Letters", "المبلغ بالحروف", "Importe en Letras", "Importo in Lettere"),
            FieldDef("currency_code", "Currency Code", "نوع العملة", "Código Moneda", "Codice Valuta", type="select", options=["USD", "EUR", "GBP", "LYD", "Other"]),
            FieldDef("percentage_tolerance", "Percentage Tolerance", "نسبة الزيادة والنقصان", "Porcentaje de Tolerancia", "Percentuale di Tolleranza"),
            FieldDef("max_credit_amount", "Maximum Credits Amount", "الحد الأقصى للاعتماد", "Importe Máximo", "Importo Massimo"),
        ],
    ),
    SectionDef(
        key="goods_services_information",
        en="Goods / Services", ar="البضاعة أو الخدمات",
        es="Bienes / Servicios", it="Merci / Servizi",
        fields=[
            FieldDef("goods_description", "Description of Goods or Services", "وصف البضاعة أو الخدمات", "Descripción de Bienes o Servicios", "Descrizione di Merci o Servizi", type="textarea", required=True),
            FieldDef("proforma_invoice_number", "Proforma Invoice / Contract No.", "حسب الفاتورة المبدئية/العقد/رقم الشراء", "Factura Proforma / Contrato", "Fattura Proforma / Contratto"),
            FieldDef("country_of_origin", "Country of Origin", "بلد المنشأ", "País de Origen", "Paese di Origine"),
            FieldDef("hs_code", "HS Code", "رمز النظام المنسق (HS)", "Código HS", "Codice HS"),
        ],
    ),
    SectionDef(
        key="lc_type_conditions",
        en="L/C Type & Conditions", ar="نوع وشروط الاعتماد",
        es="Tipo y Condiciones L/C", it="Tipo e Condizioni L/C",
        fields=[
            FieldDef("lc_type", "L/C Type", "نوع الاعتماد", "Tipo L/C", "Tipo L/C", type="select", options=["Documentary Letter of Credit", "Standby Letter of Credit"]),
            FieldDef("revolving", "Revolving", "دائري", "Rotativo", "Rotativo", type="select", options=["Yes", "No"]),
            FieldDef("irrevocable", "Irrevocable", "غير قابل للإلغاء", "Irrevocable", "Irrevocabile", type="select", options=["Yes", "No"]),
            FieldDef("transferable", "Transferable", "قابل للتحويل", "Transferible", "Trasferibile", type="select", options=["Yes", "No"]),
            FieldDef("confirmed", "Confirmed", "معزز", "Confirmado", "Confermato", type="select", options=["Yes", "No"]),
        ],
    ),
    SectionDef(
        key="shipment_details",
        en="Shipment Details", ar="تفاصيل الشحن",
        es="Detalles de Envío", it="Dettagli Spedizione",
        fields=[
            FieldDef("place_of_receipt", "Place of Taking Charge/Receipt", "مكان الشحن أو التسليم", "Lugar de Recepción", "Luogo di Presa in Carico"),
            FieldDef("port_loading", "Port of Loading / Airport of Departure", "ميناء/مطار الشحن", "Puerto de Carga", "Porto di Carico"),
            FieldDef("port_destination", "Port of Destination / Airport of Destination", "إلى ميناء/مطار الوصول", "Puerto de Destino", "Porto di Destinazione"),
            FieldDef("latest_shipment_date", "Latest Date of Shipment", "آخر تاريخ للشحن", "Fecha Límite de Envío", "Data Limite Spedizione", type="date"),
            FieldDef("partial_shipment", "Partial Shipment", "الشحن الجزئي", "Envío Parcial", "Spedizione Parziale", type="select", options=["Allowed", "Not Allowed"]),
            FieldDef("transshipment", "Transshipment", "تغيير وسيلة الشحن", "Transbordo", "Trasbordo", type="select", options=["Allowed", "Not Allowed"]),
            FieldDef("transportation_by", "Transportation By", "بواسطة", "Transporte Por", "Trasporto Via"),
        ],
    ),
    SectionDef(
        key="shipment_delivery_terms",
        en="Delivery Terms", ar="شروط التسليم",
        es="Términos de Entrega", it="Termini di Consegna",
        fields=[
            FieldDef("price_delivery_term", "Price/Delivery Term (Incoterm)", "شرط السعر والتسليم", "Incoterm", "Incoterm", type="select", options=["FOB", "CFR", "CIF", "CPT", "CIP", "Ex Works"]),
            FieldDef("named_place_port", "Named Place/Port", "المكان/الميناء المحدد", "Lugar/Puerto Designado", "Luogo/Porto Designato"),
        ],
    ),
    SectionDef(
        key="required_documents",
        en="Required Documents", ar="المستندات المطلوبة",
        es="Documentos Requeridos", it="Documenti Richiesti",
        fields=[
            FieldDef("bills_of_lading", "Full set of clean on board shipping Bills of Lading", "مجموعة كاملة من بوليصات الشحن", "Conocimientos de Embarque", "Polizze di Carico", type="checkbox"),
            FieldDef("airway_bill", "Airway Bill", "بوليصة شحن جوي", "Guía Aérea", "Lettera di Vettura Aerea", type="checkbox"),
            FieldDef("roadway_bill", "Roadway Bill", "بوليصة شحن بري", "Carta de Porte", "Lettera di Vettura", type="checkbox"),
            FieldDef("commercial_invoice", "Commercial Invoice", "فاتورة تجارية", "Factura Comercial", "Fattura Commerciale", type="checkbox"),
            FieldDef("certificate_of_origin", "Certificate of Origin", "شهادة منشأ", "Certificado de Origen", "Certificato di Origine", type="checkbox"),
            FieldDef("insurance_certificate", "Insurance Certificate", "شهادة تأمين", "Certificado de Seguro", "Certificato di Assicurazione", type="checkbox"),
            FieldDef("packing_list", "Packing List", "قائمة التعبئة", "Lista de Empaque", "Lista di Imballaggio", type="checkbox"),
            FieldDef("inspection_certificate", "Inspection Certificate", "شهادة تفتيش", "Certificado de Inspección", "Certificato di Ispezione", type="checkbox"),
            FieldDef("other_documents", "Other Documents", "مستندات أخرى", "Otros Documentos", "Altri Documenti", type="textarea"),
        ],
    ),
    SectionDef(
        key="payment_conditions",
        en="Payment Conditions", ar="شروط الدفع",
        es="Condiciones de Pago", it="Condizioni di Pagamento",
        fields=[
            FieldDef("payment_terms", "Payment Terms", "شروط الدفع", "Términos de Pago", "Termini di Pagamento"),
            FieldDef("banking_charges", "Banking Charges Outside Libya", "عمولات مصرفية خارج ليبيا", "Gastos Bancarios fuera de Libia", "Spese Bancarie fuori dalla Libia"),
        ],
    ),
    SectionDef(
        key="expiry_information",
        en="Expiry Information", ar="معلومات انتهاء الصلاحية",
        es="Información de Vencimiento", it="Informazioni Scadenza",
        fields=[
            FieldDef("expiry_date", "Expiry Date", "تاريخ انتهاء الصلاحية", "Fecha de Vencimiento", "Data di Scadenza", type="date"),
            FieldDef("place_of_expiry", "Place of Expiry", "مكان انتهاء الصلاحية", "Lugar de Vencimiento", "Luogo di Scadenza"),
        ],
    ),
    SectionDef(
        key="additional_conditions",
        en="Additional Conditions", ar="شروط أخرى",
        es="Condiciones Adicionales", it="Condizioni Aggiuntive",
        fields=[
            FieldDef("additional_conditions", "Additional Conditions", "شروط أخرى", "Condiciones Adicionales", "Condizioni Aggiuntive", type="textarea"),
        ],
    ),
    SectionDef(
        key="compliance_legal",
        en="Compliance & Legal", ar="الامتثال والقانون",
        es="Cumplimiento y Legal", it="Conformità e Legale",
        fields=[
            FieldDef("legal_representative_name", "Legal Representative Name", "اسم الممثل القانوني", "Nombre del Representante Legal", "Nome del Rappresentante Legale"),
            FieldDef("passport_number", "Passport Number", "رقم جواز السفر", "Número de Pasaporte", "Numero Passaporto"),
            FieldDef("national_id_number", "National ID Number", "الرقم الوطني", "Número de Identidad Nacional", "Numero Documento Identità"),
            FieldDef("company_name", "Company Name", "اسم الشركة", "Nombre de la Empresa", "Nome Azienda"),
            FieldDef("company_registration_number", "Company Registration Number", "رقم تسجيل الشركة", "Número de Registro", "Numero Registrazione"),
            FieldDef("company_address", "Company Address", "عنوان الشركة", "Dirección de la Empresa", "Indirizzo Azienda", type="textarea"),
            FieldDef("company_license_number", "Company License Number", "رقم رخصة الشركة", "Número de Licencia", "Numero Licenza"),
            FieldDef("chamber_of_commerce_registration", "Chamber of Commerce Registration", "تسجيل الغرفة التجارية", "Registro Cámara de Comercio", "Registrazione Camera di Commercio"),
            FieldDef("authorized_signatories", "Authorized Signatories", "المخولين بالتوقيع", "Firmantes Autorizados", "Firmatari Autorizzati", type="textarea"),
        ],
    ),
    SectionDef(
        key="financial_information",
        en="Financial Information", ar="المعلومات المالية",
        es="Información Financiera", it="Informazioni Finanziarie",
        fields=[
            FieldDef("current_account_balance_coverage", "Current Account Balance Coverage", "تغطية رصيد الحساب الجاري", "Cobertura de Saldo", "Copertura Saldo"),
            FieldDef("foreign_currency_tax_coverage", "Foreign Currency Tax Coverage", "تغطية ضريبة النقد الأجنبي", "Cobertura Impuesto Moneda Extranjera", "Copertura Fiscale Valuta Estera"),
            FieldDef("insurance_coverage", "Insurance Coverage", "تغطية التأمين", "Cobertura de Seguro", "Copertura Assicurativa"),
        ],
    ),
    SectionDef(
        key="special_conditions",
        en="Special Conditions", ar="شروط خاصة",
        es="Condiciones Especiales", it="Condizioni Speciali",
        fields=[
            FieldDef("inspection_company_name", "Inspection Company Name", "اسم شركة التفتيش", "Nombre Empresa de Inspección", "Nome Società di Ispezione"),
            FieldDef("central_bank_approval", "Central Bank of Libya Approval", "موافقة مصرف ليبيا المركزي", "Aprobación del Banco Central de Libia", "Approvazione Banca Centrale di Libia", type="checkbox"),
            FieldDef("anti_money_laundering_compliance", "Anti-Money Laundering Compliance", "الامتثال لمكافحة غسل الأموال", "Cumplimiento Anti-Lavado", "Conformità Antiriciclaggio", type="checkbox"),
            FieldDef("icc_rules_compliance", "ICC Rules Compliance", "الامتثال لقواعد غرفة التجارة الدولية", "Cumplimiento Reglas ICC", "Conformità Regole ICC", type="checkbox"),
        ],
    ),
]

# ── Helper functions ──────────────────────────────────────────────────────────

def get_all_fields() -> list[FieldDef]:
    """Return a flat list of all fields across all sections."""
    fields = []
    for section in SECTIONS:
        for f in section.fields:
            f.section = section.key
            fields.append(f)
    return fields


def get_extractable_fields() -> list[FieldDef]:
    """Return only fields that can be extracted from documents."""
    return [f for f in get_all_fields() if f.extractable and f.type not in ("file", "signature", "stamp")]


def get_field_map() -> dict[str, FieldDef]:
    """Return {field_key: FieldDef} map."""
    return {f.key: f for f in get_all_fields()}


def build_extraction_json_keys() -> dict[str, str]:
    """Build {field_key: "value or null"} for the extraction prompt."""
    return {f.key: "value or null" for f in get_extractable_fields()}


def build_field_hints(lang: str = "en") -> str:
    """Build a human-readable field reference for LLM prompts."""
    lines = []
    for f in get_extractable_fields():
        en_label = f.en
        ar_label = f.ar
        lines.append(f'  "{f.key}": "{en_label}" / "{ar_label}"')
    return "\n".join(lines)


def get_sections_as_dict(lang: str = "en") -> list[dict]:
    """Export sections as JSON-serializable dicts for the frontend."""
    result = []
    for section in SECTIONS:
        s = {
            "key": section.key,
            "label": section.label(lang),
            "label_ar": section.ar,
            "fields": [],
        }
        for f in section.fields:
            fd = {
                "key": f.key,
                "label": f.label(lang),
                "label_ar": f.ar,
                "type": f.type,
                "required": f.required,
            }
            if f.options:
                fd["options"] = f.options
            s["fields"].append(fd)
        result.append(s)
    return result
