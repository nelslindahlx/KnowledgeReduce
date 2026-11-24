import PyPDF2

# Open the PDF file
pdf_path = '/home/ubuntu/upload/KnowledgeReduce__Building_Stackable_Knowledge v4.pdf'
pdf = PyPDF2.PdfReader(pdf_path)

# Extract text from each page
text = ""
for page in pdf.pages:
    text += page.extract_text() + "\n\n"

# Save the extracted text to a file
output_path = '/home/ubuntu/knowledge_repo/paper_content.txt'
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(text)

print(f"PDF content extracted successfully and saved to {output_path}")
