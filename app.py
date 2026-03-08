import os, json, pandas as pd, numpy as np
from flask import Flask, render_template, request, jsonify, session
from groq import Groq

try:
    import fitz # PyMuPDF
except ImportError:
    fitz = None

app = Flask(__name__)
app.secret_key = "smart_report_pro_v4_final"
client = Groq(api_key="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")

def get_precision_prompt(data_context, lang, data_type):
    lang_rule = f"STRICT RULE: All content, headers, and labels must be in {lang}. Do NOT use numbering for sections (like 1, 2, 3). Use bullet points if needed."
    
    if data_type == "numeric":
        return f"""Analyze this data: {data_context}. 
        {lang_rule}
        Return JSON with:
        - title: Professional title.
        - introduction: Overview of the data.
        - data_nature: Analysis of structure.
        - stats_table_html: Styled HTML table (Add class='styled-table' to the table tag).
        - strategic_recommendations: List of insights.
        """
    else:
        return f"""Analyze this text: {data_context}. 
        {lang_rule}
        Return JSON with:
        - title: Professional title.
        - content_overview: Document purpose.
        - executive_summary_15_lines: Detailed summary.
        - recommendations: List of actionable steps.
        """

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    file = request.files.get('file')
    lang = request.form.get('lang', 'Arabic')
    if not file: return jsonify({'error': 'No file'}), 400
    
    ext = file.filename.split('.')[-1].lower()
    try:
        if ext in ['csv', 'xlsx', 'xls']:
            df = pd.read_csv(file) if ext == 'csv' else pd.read_excel(file)
            stats = df.describe().round(2).to_dict()
            metadata = {"columns": list(df.columns), "stats": stats}
            prompt = get_precision_prompt(metadata, lang, "numeric")
            num_df = df.select_dtypes(include=[np.number])
            cols = list(num_df.columns)[:5]
            charts = {"labels": cols, "values": [round(float(df[c].mean()), 2) for c in cols]}
            file_type = "numeric"
        else:
            doc = fitz.open(stream=file.read(), filetype="pdf")
            full_text = "".join([page.get_text() for page in doc])
            prompt = get_precision_prompt(full_text[:12000], lang, "text")
            charts, file_type = None, "text"

        res = client.chat.completions.create(
            messages=[{"role": "system", "content": "Return JSON only."}, {"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"}
        )
        report_data = json.loads(res.choices[0].message.content)
        session['report'] = report_data
        return jsonify({'report': report_data, 'charts': charts, 'type': file_type, 'lang': lang})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/chat', methods=['POST'])
def chat():
    query = request.json.get('query')
    context = session.get('report', {})
    system_msg = f"""You are a specialized assistant for this report only: {context}. 
    - ONLY answer questions based on this data. 
    - If the user asks anything outside this report or data, reply: 'I am specialized only in analyzing this report.'
    - Respond in the language of the query."""
    
    res = client.chat.completions.create(
        messages=[{"role": "system", "content": system_msg}, {"role": "user", "content": query}],
        model="llama-3.3-70b-versatile"
    )
    return jsonify({'answer': res.choices[0].message.content})

if __name__ == '__main__':
    app.run(debug=True)