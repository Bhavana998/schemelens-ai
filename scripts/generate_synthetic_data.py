"""
Generates synthetic, realistic, clearly labelled government welfare scheme documents
and their corresponding ground-truth JSON annotations for SchemeLens AI evaluation.

Fixtures created in data/sample_documents/:
1. kisan_samriddhi_yojana.pdf - English circular with complete fields.
2. mahila_swavalamban_yojana.pdf - Hindi notification with missing deadline & official link.
3. yuva_kaushal_scanned.pdf - Pure image-based scanned PDF to exercise OCR fallback.
4. kisan_samriddhi_revised_circular.pdf - Amended circular with conflicting amount & deadline.

Ground truth created in data/ground_truth/synthetic_ground_truth.json.
"""

import io
import json
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import pymupdf as fitz


def get_system_font_or_default():
    """Locate a system TTF/TTC font supporting Devanagari or fallback."""
    candidate_hindi_fonts = [
        r"C:\Windows\Fonts\Nirmala.ttc",
        r"C:\Windows\Fonts\Nirmala.ttf",
        r"C:\Windows\Fonts\mangal.ttf",
        r"C:\Windows\Fonts\aparaj.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    ]
    for font_path in candidate_hindi_fonts:
        if os.path.exists(font_path):
            return font_path
    return None


def create_english_scheme_pdf(output_path: Path):
    """Creates synthetic English scheme PDF (kisan_samriddhi_yojana.pdf)."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4

    text = """GOVERNMENT WELFARE MISSION (SYNTHETIC BENCHMARK DOCUMENT)
DEPARTMENT OF AGRICULTURE & FARMERS WELFARE (SYNTHETIC)
NOTIFICATION REF: SYN-AGRI-2024-001 | DATE: 15 JANUARY 2024

SCHEME GUIDELINES: KISAN SAMRIDDHI SUPPORT YOJANA (SYNTHETIC)

1. OBJECTIVE & SCHEME NAME
The Department of Agriculture & Farmers Welfare (Synthetic) announces the implementation of the "Kisan Samriddhi Support Yojana (Synthetic)" to provide income support to vulnerable cultivating households across participating districts.

2. BENEFIT TYPE AND FINANCIAL ASSISTANCE
Under this welfare initiative, eligible beneficiaries shall receive Direct Cash Transfer. The scheme provides a guaranteed financial assistance of Rs. 6,000 per year directly into the bank account of the beneficiary farmer. The benefit frequency is Annual, disbursed in three equal installments of Rs. 2,000 every four months.

3. ELIGIBILITY CONDITIONS
To be eligible for the scheme, applicants must satisfy all of the following criteria:
a) Small and marginal farmers owning cultivable agricultural land up to 2 hectares as per official land records.
b) Applicant must be a resident citizen possessing a valid Aadhaar number linked to their primary bank account.
c) Institutional landholders, serving government officials, and income-tax payees are strictly excluded from receiving benefits.

4. REQUIRED DOCUMENTS
Applicants must furnish self-attested copies of the following documents:
1. Aadhaar Card (mandatory identity proof)
2. Land Ownership Record (Khatauni or Khasra certificate)
3. Active Bank Account Passbook with clearly legible IFSC code

5. APPLICATION PROCEDURE
Eligible farmers can submit applications through the official web portal or visit their local Common Service Centre (CSC) for assisted biometric registration. The designated Block Agriculture Officer shall verify field claims within 21 working days of submission.

6. APPLICATION DEADLINE & OFFICIAL CITATION
The final deadline for enrolling under the current fiscal cycle is 31 March 2025.
Official scheme information and application forms can be accessed at:
https://synthetic-portal.gov.in/schemes/kisan-samriddhi

DISCLAIMER: This document is an entirely synthetic test fixture created strictly for software evaluation and testing purposes. It does not represent any real-world scheme or legal notification.
"""
    rect = fitz.Rect(40, 40, 555, 800)
    page.insert_textbox(rect, text, fontsize=10, fontname="helv", align=0)
    doc.save(str(output_path))
    doc.close()
    print(f"Created: {output_path}")


def create_revised_conflicting_pdf(output_path: Path):
    """Creates synthetic revised circular with conflicting benefit amount & deadline."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)

    text = """GOVERNMENT WELFARE MISSION (SYNTHETIC BENCHMARK DOCUMENT)
DEPARTMENT OF AGRICULTURE & FARMERS WELFARE (SYNTHETIC)
CIRCULAR REF: SYN-AGRI-2024-REV-09B | DATE: 20 NOVEMBER 2024

SUBJECT: AMENDMENT TO BENEFIT AMOUNT AND TIMELINE UNDER KISAN SAMRIDDHI SUPPORT YOJANA (SYNTHETIC)

In continuation of the earlier notification SYN-AGRI-2024-001, the Department of Agriculture & Farmers Welfare (Synthetic) hereby notifies the following revisions:

1. REVISION OF BENEFIT AMOUNT
In view of increased cultivation and input expenditure, the financial assistance is hereby revised to Rs. 8,000 per year. The revised benefit frequency shall be four quarterly installments of Rs. 2,000 credited through Direct Benefit Transfer (Cash Transfer).

2. EXTENSION OF ENROLLMENT DEADLINE
Considering the ongoing seasonal planting, the competent authority has extended the application deadline to 30 June 2025. All pending applications received before this date shall be processed under the revised scale.

3. OTHER CONDITIONS
All other eligibility conditions, required documents (Aadhaar, Khatauni, Bank Passbook), and the official portal remain unchanged as notified earlier.

APPROVED BY:
Competent Authority, Department of Agriculture & Farmers Welfare (Synthetic)
Official Citation: https://synthetic-portal.gov.in/schemes/kisan-samriddhi

DISCLAIMER: This is a synthetic conflict-test fixture designed to evaluate automated contradiction detection.
"""
    rect = fitz.Rect(40, 40, 555, 800)
    page.insert_textbox(rect, text, fontsize=10, fontname="helv", align=0)
    doc.save(str(output_path))
    doc.close()
    print(f"Created: {output_path}")


def create_hindi_scheme_pdf(output_path: Path):
    """Creates synthetic Hindi scheme PDF with missing deadline and official link."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    font_file = get_system_font_or_default()

    hindi_text = """कल्याणकारी योजना सूचना (सिंथेटिक परीक्षण दस्तावेज़)
विभाग: महिला एवं बाल विकास विभाग (सिंथेटिक)
अधिसूचना क्रमांक: SYN-WCD-2024-102 | दिनांक: 10 फरवरी 2024

योजना का नाम: महिला स्वावलंबन स्वरोजगार योजना (सिंथेटिक)

1. योजना का उद्देश्य
महिला एवं बाल विकास विभाग (सिंथेटिक) द्वारा ग्रामीण एवं अर्ध-शहरी क्षेत्रों की महिलाओं को आत्मनिर्भर बनाने हेतु "महिला स्वावलंबन स्वरोजगार योजना (सिंथेटिक)" संचालित की जा रही है।

2. लाभ का प्रकार एवं वित्तीय सहायता
यह योजना बैंक ऋण पर पूंजीगत सब्सिडी (Subsidy) प्रदान करती है। चयनित महिला उद्यमी को सूक्ष्म उद्यम स्थापना हेतु रु 50,000 की पूंजीगत सब्सिडी एकमुश्त (One-time) बैंक खाते में प्रदान की जाएगी।

3. पात्रता शर्तें
योजना का लाभ प्राप्त करने हेतु निम्नलिखित पात्रता अनिवार्य है:
क) आवेदक महिला की आयु 18 से 50 वर्ष के मध्य होनी चाहिए।
ख) परिवार की कुल वार्षिक आय रु 1,50,000 से अधिक नहीं होनी चाहिए।
ग) आवेदक महिला किसी पंजीकृत स्वयं सहायता समूह (SHG) की सक्रिय सदस्य होनी चाहिए।

4. आवश्यक दस्तावेज
आवेदन के साथ निम्नलिखित प्रमाण पत्र संलग्न करें:
1. आधार कार्ड
2. पारिवारिक आय प्रमाण पत्र (सक्षम राजस्व अधिकारी द्वारा निर्गत)
3. मूल निवास प्रमाण पत्र
4. बैंक खाता पासबुक की प्रति

5. आवेदन की प्रक्रिया
इच्छुक महिलाएं निर्धारित आवेदन पत्र भरकर अपने निकटतम जिला महिला कल्याण अधिकारी कार्यालय अथवा ग्राम पंचायत विकास केंद्र में जमा कर सकती हैं।

[सूचना: इस अधिसूचना में कोई निश्चित अंतिम तिथि अथवा आधिकारिक वेबसाइट लिंक विनिर्दिष्ट नहीं है। योजना वर्ष पर्यंत खुली रहती है।]

अस्वीकरण: यह पूर्णतः काल्पनिक एवं सिंथेटिक दस्तावेज़ है। इसका उपयोग केवल सॉफ्टवेयर परीक्षण हेतु किया गया है।
"""
    rect = fitz.Rect(40, 40, 555, 800)
    if font_file:
        try:
            page.insert_font(fontname="hindi_font", fontfile=font_file)
            page.insert_textbox(rect, hindi_text, fontsize=10, fontname="hindi_font", align=0)
        except Exception:
            # Fallback text rendering if font registration encounters system limits
            page.insert_textbox(rect, hindi_text, fontsize=10, fontname="helv", align=0)
    else:
        page.insert_textbox(rect, hindi_text, fontsize=10, fontname="helv", align=0)

    doc.save(str(output_path))
    doc.close()
    print(f"Created: {output_path}")


def create_scanned_scheme_pdf(output_path: Path):
    """
    Creates an image-based / scanned PDF without text layer.
    Forces the ingestion engine to fall back to Tesseract OCR.
    """
    width, height = 1200, 1600
    image = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(image)

    # Use standard default PIL font or system font
    try:
        font_title = ImageFont.truetype("arial.ttf", 36)
        font_body = ImageFont.truetype("arial.ttf", 26)
        font_small = ImageFont.truetype("arial.ttf", 20)
    except Exception:
        font_title = ImageFont.load_default()
        font_body = font_title
        font_small = font_title

    lines = [
        ("GOVERNMENT OF STATE WELFARE (SCANNED SYNTHETIC DOCUMENT)", font_title, (20, 20, 80)),
        ("DEPARTMENT: Ministry of Skill Development and Entrepreneurship (Synthetic)", font_body, (30, 30, 30)),
        ("NOTIFICATION NO: MSD-SYN-2024-44 | DATED: 05 MAY 2024", font_small, (80, 80, 80)),
        ("", font_body, (0, 0, 0)),
        ("SCHEME: Yuva Kaushal Stipend Program (Synthetic)", font_title, (0, 70, 130)),
        ("", font_body, (0, 0, 0)),
        ("1. BENEFIT TYPE AND STIPEND AMOUNT:", font_body, (0, 0, 0)),
        ("Under this skill program, registered apprentices receive Skill / Training with", font_body, (40, 40, 40)),
        ("a monthly financial stipend of Rs. 3,500 monthly stipend during training.", font_body, (40, 40, 40)),
        ("The benefit frequency is Monthly throughout the six-month apprenticeship.", font_body, (40, 40, 40)),
        ("", font_body, (0, 0, 0)),
        ("2. ELIGIBILITY CONDITIONS:", font_body, (0, 0, 0)),
        ("- Youth between 18 and 29 years of age residing in the state.", font_body, (40, 40, 40)),
        ("- Minimum educational qualification of 10th standard pass from recognized board.", font_body, (40, 40, 40)),
        ("- Must be currently unemployed and not enrolled in regular college.", font_body, (40, 40, 40)),
        ("", font_body, (0, 0, 0)),
        ("3. REQUIRED DOCUMENTS:", font_body, (0, 0, 0)),
        ("1. 10th Standard Marks Sheet and Passing Certificate", font_body, (40, 40, 40)),
        ("2. Aadhaar Card for identity verification", font_body, (40, 40, 40)),
        ("3. Bank Account Passbook", font_body, (40, 40, 40)),
        ("", font_body, (0, 0, 0)),
        ("4. APPLICATION PROCEDURE:", font_body, (0, 0, 0)),
        ("Candidates must register at the nearest District Skill Development Centre (DSDC)", font_body, (40, 40, 40)),
        ("with physical copies of their documents.", font_body, (40, 40, 40)),
        ("", font_body, (0, 0, 0)),
        ("5. ENROLLMENT DEADLINE: 15 December 2025", font_body, (0, 0, 0)),
        ("", font_body, (0, 0, 0)),
        ("NOTE: Official web portal link is not provided in this physical bulletin.", font_small, (100, 100, 100)),
        ("DISCLAIMER: Strictly synthetic image-based fixture for OCR validation.", font_small, (120, 120, 120)),
    ]

    y = 60
    for text_line, font, color in lines:
        draw.text((60, y), text_line, fill=color, font=font)
        y += 48 if font == font_title else 38

    # Save image to byte stream and insert into PDF
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format="PNG")
    img_bytes = img_byte_arr.getvalue()

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_image(page.rect, stream=img_bytes)
    doc.save(str(output_path))
    doc.close()
    print(f"Created scanned PDF: {output_path}")


def create_ground_truth_json(output_path: Path):
    """
    Generates verifiable ground-truth annotations for all synthetic schemes.
    Used for field-level exact matching, evidence citation verification,
    missing field detection, and conflict evaluation.
    """
    ground_truth = {
        "kisan_samriddhi_yojana.pdf": {
            "scheme_name": {
                "value": "Kisan Samriddhi Support Yojana (Synthetic)",
                "evidence_quote": "Kisan Samriddhi Support Yojana (Synthetic)",
                "page": 1,
                "status": "found"
            },
            "department": {
                "value": "Department of Agriculture & Farmers Welfare (Synthetic)",
                "evidence_quote": "Department of Agriculture & Farmers Welfare (Synthetic)",
                "page": 1,
                "status": "found"
            },
            "benefit_type": {
                "value": "Direct Cash Transfer",
                "evidence_quote": "Direct Cash Transfer",
                "page": 1,
                "status": "found"
            },
            "benefit_amount": {
                "value": "Rs. 6,000 per year",
                "evidence_quote": "guaranteed financial assistance of Rs. 6,000 per year",
                "page": 1,
                "status": "found"
            },
            "benefit_frequency": {
                "value": "Annual, paid in three equal installments of Rs. 2,000 every four months",
                "evidence_quote": "benefit frequency is Annual, disbursed in three equal installments of Rs. 2,000 every four months",
                "page": 1,
                "status": "found"
            },
            "eligibility_conditions": {
                "value": "Small and marginal farmers owning cultivable agricultural land up to 2 hectares, subject to the additional eligibility and exclusion conditions stated in the PDF",
                "evidence_quote": "Small and marginal farmers owning cultivable agricultural land up to 2 hectares as per official land records",
                "page": 1,
                "status": "found"
            },
            "required_documents": {
                "value": "Aadhaar Card, Land Ownership Record (Khatauni or Khasra certificate), and active bank account passbook with IFSC code",
                "evidence_quote": "Aadhaar Card (mandatory identity proof)",
                "page": 1,
                "status": "found"
            },
            "application_procedure": {
                "value": "Official web portal or local Common Service Centre (CSC); the Block Agriculture Officer verifies field claims within 21 working days of submission",
                "evidence_quote": "submit applications through the official web portal or visit their local Common Service Centre (CSC)",
                "page": 1,
                "status": "found"
            },
            "deadline": {
                "value": "31 March 2025",
                "evidence_quote": "final deadline for enrolling under the current fiscal cycle is 31 March 2025",
                "page": 1,
                "status": "found"
            },
            "official_link": {
                "value": "https://synthetic-portal.gov.in/schemes/kisan-samriddhi",
                "evidence_quote": "https://synthetic-portal.gov.in/schemes/kisan-samriddhi",
                "page": 1,
                "status": "found"
            }
        },
        "kisan_samriddhi_revised_circular.pdf": {
            "scheme_name": {
                "value": "Kisan Samriddhi Support Yojana (Synthetic)",
                "evidence_quote": "Kisan Samriddhi Support Yojana (Synthetic)",
                "page": 1,
                "status": "found"
            },
            "department": {
                "value": "Department of Agriculture & Farmers Welfare (Synthetic)",
                "evidence_quote": "Department of Agriculture & Farmers Welfare (Synthetic)",
                "page": 1,
                "status": "found"
            },
            "benefit_type": {
                "value": "Cash Transfer",
                "evidence_quote": "Direct Benefit Transfer (Cash Transfer)",
                "page": 1,
                "status": "found"
            },
            "benefit_amount": {
                "value": "Rs. 8,000 per year",
                "evidence_quote": "financial assistance is hereby revised to Rs. 8,000 per year",
                "page": 1,
                "status": "conflict"
            },
            "benefit_frequency": {
                "value": "Quarterly",
                "evidence_quote": "revised benefit frequency shall be four quarterly installments",
                "page": 1,
                "status": "conflict"
            },
            "deadline": {
                "value": "30 June 2025",
                "evidence_quote": "extended the application deadline to 30 June 2025",
                "page": 1,
                "status": "conflict"
            },
            "official_link": {
                "value": "https://synthetic-portal.gov.in/schemes/kisan-samriddhi",
                "evidence_quote": "https://synthetic-portal.gov.in/schemes/kisan-samriddhi",
                "page": 1,
                "status": "found"
            }
        },
        "mahila_swavalamban_yojana.pdf": {
            "scheme_name": {
                "value": "महिला स्वावलंबन स्वरोजगार योजना (सिंथेटिक)",
                "evidence_quote": "महिला स्वावलंबन स्वरोजगार योजना (सिंथेटिक)",
                "page": 1,
                "status": "found"
            },
            "department": {
                "value": "महिला एवं बाल विकास विभाग (सिंथेटिक)",
                "evidence_quote": "महिला एवं बाल विकास विभाग (सिंथेटिक)",
                "page": 1,
                "status": "found"
            },
            "benefit_type": {
                "value": "Subsidy",
                "evidence_quote": "पूंजीगत सब्सिडी (Subsidy)",
                "page": 1,
                "status": "found"
            },
            "benefit_amount": {
                "value": "रु 50,000",
                "evidence_quote": "रु 50,000 की पूंजीगत सब्सिडी",
                "page": 1,
                "status": "found"
            },
            "benefit_frequency": {
                "value": "One-time",
                "evidence_quote": "एकमुश्त (One-time)",
                "page": 1,
                "status": "found"
            },
            "eligibility_conditions": {
                "value": [
                    "आवेदक महिला की आयु 18 से 50 वर्ष के मध्य होनी चाहिए",
                    "परिवार की कुल वार्षिक आय रु 1,50,000 से अधिक नहीं होनी चाहिए",
                    "स्वयं सहायता समूह (SHG) की सक्रिय सदस्य होनी चाहिए"
                ],
                "evidence_quote": "आवेदक महिला की आयु 18 से 50 वर्ष के मध्य होनी चाहिए",
                "page": 1,
                "status": "found"
            },
            "required_documents": {
                "value": [
                    "आधार कार्ड",
                    "पारिवारिक आय प्रमाण पत्र",
                    "मूल निवास प्रमाण पत्र",
                    "बैंक खाता पासबुक की प्रति"
                ],
                "evidence_quote": "आधार कार्ड",
                "page": 1,
                "status": "found"
            },
            "application_procedure": {
                "value": "आवेदन पत्र जिला महिला कल्याण अधिकारी कार्यालय अथवा ग्राम पंचायत विकास केंद्र में जमा करें",
                "evidence_quote": "जिला महिला कल्याण अधिकारी कार्यालय अथवा ग्राम पंचायत विकास केंद्र में जमा",
                "page": 1,
                "status": "found"
            },
            "deadline": {
                "value": None,
                "evidence_quote": None,
                "page": None,
                "status": "not_found",
                "expected_missing": True,
                "rationale": "No enrollment deadline specified in document"
            },
            "official_link": {
                "value": None,
                "evidence_quote": None,
                "page": None,
                "status": "not_found",
                "expected_missing": True,
                "rationale": "No official link provided in document"
            }
        },
        "yuva_kaushal_scanned.pdf": {
            "scheme_name": {
                "value": "Yuva Kaushal Stipend Program (Synthetic)",
                "evidence_quote": "Yuva Kaushal Stipend Program (Synthetic)",
                "page": 1,
                "status": "found"
            },
            "department": {
                "value": "Ministry of Skill Development and Entrepreneurship (Synthetic)",
                "evidence_quote": "Ministry of Skill Development and Entrepreneurship (Synthetic)",
                "page": 1,
                "status": "found"
            },
            "benefit_type": {
                "value": "Skill / Training",
                "evidence_quote": "Skill / Training",
                "page": 1,
                "status": "found"
            },
            "benefit_amount": {
                "value": "Rs. 3,500 monthly stipend",
                "evidence_quote": "Rs. 3,500 monthly stipend during training",
                "page": 1,
                "status": "found"
            },
            "benefit_frequency": {
                "value": "Monthly",
                "evidence_quote": "benefit frequency is Monthly",
                "page": 1,
                "status": "found"
            },
            "deadline": {
                "value": "15 December 2025",
                "evidence_quote": "ENROLLMENT DEADLINE: 15 December 2025",
                "page": 1,
                "status": "found"
            },
            "official_link": {
                "value": None,
                "evidence_quote": None,
                "page": None,
                "status": "not_found",
                "expected_missing": True,
                "rationale": "No web portal link in physical scanned bulletin"
            }
        }
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(ground_truth, f, indent=2, ensure_ascii=False)
    print(f"Created ground-truth: {output_path}")


def main():
    base_dir = Path(__file__).resolve().parent.parent
    docs_dir = base_dir / "data" / "sample_documents"
    gt_dir = base_dir / "data" / "ground_truth"
    docs_dir.mkdir(parents=True, exist_ok=True)
    gt_dir.mkdir(parents=True, exist_ok=True)

    create_english_scheme_pdf(docs_dir / "kisan_samriddhi_yojana.pdf")
    create_revised_conflicting_pdf(docs_dir / "kisan_samriddhi_revised_circular.pdf")
    create_hindi_scheme_pdf(docs_dir / "mahila_swavalamban_yojana.pdf")
    create_scanned_scheme_pdf(docs_dir / "yuva_kaushal_scanned.pdf")
    create_ground_truth_json(gt_dir / "synthetic_ground_truth.json")
    print("Synthetic dataset generation completed successfully.")


if __name__ == "__main__":
    main()
