from flask import Flask, request, jsonify
import pdfplumber, base64, re, io

app = Flask(__name__)

def extract_fields(text):
    na = lambda v: v.strip() if v and v.strip() else "NA"
    lines = [l.strip() for l in text.splitlines()]
    flat  = re.sub(r"\s+", " ", text)

    data = {
        "invoice_no":"","date":"","bus_gst":"","gstin":"","customer_name":"",
        "location":"","business_name":"","operator_name":"","origin":"","destination":"",
        "bus_fare":"","IGST@5%":"0","CGST@2.5%":"0","SGST@2.5%":"0","total":"",
        "doc_type":"","hsn":"","pnr":"","cancellation_date":"","additional_services":"",
        "other_charges":"","non_refundable_charges":"","tin":""
    }

    m = re.search(r"([A-Z0-9\-]+)\s+(\d{2}/\d{2}/\d{4})", flat)
    if m: data["invoice_no"],data["date"] = m.group(1),m.group(2)

    m = re.search(r"\b[0-9A-Z]{15}\b", flat)
    if m: data["gstin"] = m.group(0)

    for i,line in enumerate(lines):
        if "customer name" in line.lower():
            parts = re.split(r"\t+|\s{2,}", lines[i+1] if i+1<len(lines) else "")
            data["customer_name"] = (parts[0] if parts else "").strip(); break

    for i,line in enumerate(lines):
        if "location" in line.lower():
            l1 = lines[i+1] if i+1<len(lines) else ""
            l2 = lines[i+2] if i+2<len(lines) else ""
            data["location"] = f"{l1},{l2}".strip(","); break

    for i,line in enumerate(lines):
        if "business name" in line.lower():
            data["business_name"] = (lines[i+1] if i+1<len(lines) else "").strip(); break

    for i,line in enumerate(lines):
        if "bus operator name" in line.lower():
            data["operator_name"] = (lines[i+1] if i+1<len(lines) else "").strip(); break

    for i,line in enumerate(lines):
        if re.search(r"\bTIN\b", line):
            nm = re.search(r"([A-Z0-9]{6,12})$", lines[i+1] if i+1<len(lines) else "")
            if nm: data["tin"] = nm.group(1); break

    for i,line in enumerate(lines):
        if "origin" in line.lower():
            parts = re.split(r"\t+|\s{2,}", lines[i+1] if i+1<len(lines) else "")
            data["origin"] = (parts[0] if parts else "").strip(); break

    for i,line in enumerate(lines):
        if "destination" in line.lower():
            parts = re.split(r"\t+|\s{2,}", lines[i+1] if i+1<len(lines) else "")
            data["destination"] = (parts[0] if parts else "").strip(); break

    m = re.search(r"Total Invoice Value\s+([\d,]+\.\d+)", flat, re.IGNORECASE)
    if m: data["total"] = m.group(1)

    m = re.search(r"\bINVOICE\b", flat, re.IGNORECASE)
    if m: data["doc_type"] = m.group(0)

    for i,line in enumerate(lines):
        if "pnr" in line.lower():
            for j in range(1,6):
                check = lines[i+j] if i+j<len(lines) else ""
                pm = re.search(r"([A-Z0-9\-]{6,})\s+(\d{4,8})", check, re.IGNORECASE)
                if pm: data["pnr"]=pm.group(1); data["hsn"]=pm.group(2); break
            break

    for i,line in enumerate(lines):
        if "gst number" in line.lower():
            combined = line + " " + (lines[i+1] if i+1<len(lines) else "")
            gm = re.search(r"\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][A-Z0-9]{3}\b", combined)
            if gm: data["bus_gst"] = gm.group(0); break

    for line in lines:
        if "bus fare" in line.lower():
            fm = re.search(r"Bus Fare\s*(.*)$", line, re.IGNORECASE)
            if fm: data["bus_fare"] = fm.group(1).strip(); break

    for line in lines:
        if "additional services" in line.lower():
            fm = re.search(r"Additional Services\s*(.*)$", line, re.IGNORECASE)
            if fm: data["additional_services"] = fm.group(1).strip(); break

    for line in lines:
        if "other charges" in line.lower():
            fm = re.search(r"Other charges.*?\s+([A-Z\/]+|[\d,]+\.\d{2})$", line, re.IGNORECASE)
            if fm: data["other_charges"] = fm.group(1).strip(); break

    for i,line in enumerate(lines):
        if "non-refundable charges" in line.lower():
            fm = re.search(r"Non-Refundable Charges.*?([\d,]+\.\d{2})", line, re.IGNORECASE)
            if fm:
                data["non_refundable_charges"] = fm.group(1).replace(",","")
            else:
                nm = re.search(r"([\d,]+\.\d{2})", lines[i+1] if i+1<len(lines) else "")
                data["non_refundable_charges"] = nm.group(1).replace(",","") if nm else ""
            break

    flat2 = re.sub(r"\s+", " ", text)
    for key,pat in [("IGST@5%",r"IGST\s*@\s*[\d.]+%\s*([\d,]+\.\d{2})"),
                    ("CGST@2.5%",r"CGST\s*@\s*[\d.]+%\s*([\d,]+\.\d{2})"),
                    ("SGST@2.5%",r"SGST\s*@\s*[\d.]+%\s*([\d,]+\.\d{2})")]:
        m = re.search(pat, flat2, re.IGNORECASE)
        data[key] = m.group(1).replace(",","") if m else "0"

    for i,line in enumerate(lines):
        if "cancellation date" in line.lower():
            dm = re.search(r"(\d{2}[\/\-]\d{2}[\/\-]\d{4})", line)
            if dm:
                data["cancellation_date"] = dm.group(1)
            else:
                nm = re.search(r"(\d{2}[\/\-]\d{2}[\/\-]\d{4})", lines[i+1] if i+1<len(lines) else "")
                data["cancellation_date"] = nm.group(1) if nm else (lines[i+1] if i+1<len(lines) else "")
            break

    data["hsn"]                    = na(data["hsn"])
    data["cancellation_date"]      = na(data["cancellation_date"])
    data["non_refundable_charges"] = na(data["non_refundable_charges"])
    return data


@app.route("/extract", methods=["POST"])
def extract():
    body      = request.get_json()
    b64       = body.get("pdfBase64","")
    file_name = body.get("fileName","invoice.pdf")

    # ── Strip data-URL prefix if present ─────────────────────────────
    if "," in b64:
        b64 = b64.split(",", 1)[1]
    
    try:
        pdf_bytes = base64.b64decode(b64)
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            text = "\n".join(p.extract_text() or "" for p in pdf.pages)

        if not text.strip():
            return jsonify({"STATUS":"UNREADABLE","File Name":file_name})

        f = extract_fields(text)

        def num(v):
            try: return float(str(v).replace(",","").strip()) if v and str(v).strip() not in ("","NA") else 0.0
            except: return 0.0

        return jsonify({
            "File Name":              file_name,
            "invoice_no":             f["invoice_no"],
            "date":                   f["date"],
            "bus_gst":                f["bus_gst"],
            "gstin":                  f["gstin"],
            "customer_name":          f["customer_name"],
            "location":               f["location"],
            "business_name":          f["business_name"],
            "operator_name":          f["operator_name"],
            "origin":                 f["origin"],
            "destination":            f["destination"],
            "bus_fare":               num(f["bus_fare"]),
            "IGST@5%":                num(f["IGST@5%"]),
            "CGST@2.5%":              num(f["CGST@2.5%"]),
            "SGST@2.5%":              num(f["SGST@2.5%"]),
            "total":                  num(f["total"]),
            "doc_typ":                f["doc_type"],
            "hsn":                    f["hsn"],
            "pnr":                    f["pnr"],
            "cancellation_date":      f["cancellation_date"],
            "additional_services":    num(f["additional_services"]),
            "other_charges":          num(f["other_charges"]),
            "non_refundable_charges": num(f["non_refundable_charges"]),
            "tin":                    f["tin"],
            "STATUS":                 "✅ Processed",
        })

    except Exception as e:
        return jsonify({"STATUS": f"❌ ERROR: {str(e)[:200]}", "File Name": file_name}), 500


# if __name__ == "__main__":
#     app.run(host="0.0.0.0", port=8000)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
