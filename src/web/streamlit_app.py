"""
Streamlit Web Application for Invoice Parser
"""

import streamlit as st  # type: ignore
import pandas as pd  # type: ignore
import json
from pathlib import Path
from PIL import Image
from typing import cast
import io
import sys
import os

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.absolute()
sys.path.insert(0, str(project_root))
os.chdir(project_root)  # Change working directory to project root

from ..extraction import InvoiceExtractor
from ..extraction.invoice_extractor import InvoiceData
from ..core import get_config


# Page configuration
st.set_page_config(
    page_title="Invoice Parser",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)


# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .success-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
    }
    .info-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #cce5ff;
        border: 1px solid #b8daff;
        color: #004085;
    }
    .metric-card {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def load_extractor(ocr_engine: str, languages: list, use_gpu: bool):
    """Load and cache the invoice extractor"""
    return InvoiceExtractor(
        ocr_engine=ocr_engine,
        languages=languages,
        use_gpu=use_gpu,
    )


def main():
    # Header
    st.markdown('<h1 class="main-header">📄 Invoice Parser</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p style="text-align: center; color: gray;">AI-powered Invoice/Receipt Parser using OCR</p>',
        unsafe_allow_html=True
    )
    
    # Sidebar configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        ocr_engine = st.selectbox(
            "OCR Engine",
            options=["paddleocr", "easyocr"],
            index=0,
            help="Select the OCR engine to use"
        )
        
        languages = st.multiselect(
            "Languages",
            options=["en", "vi", "zh", "ja", "ko", "fr", "de"],
            default=["en"],
            help="Select languages for OCR"
        )
        
        use_gpu = st.checkbox(
            "Use GPU",
            value=False,
            help="Enable GPU acceleration (requires CUDA)"
        )
        
        st.divider()
        
        st.header("📊 About")
        st.markdown("""
        This application uses:
        - **PaddleOCR/EasyOCR** for text detection
        - **Rule-based extraction** for field parsing
        - **LayoutLMv3** (optional) for document understanding
        """)
        
        st.divider()
        
        st.header("📋 Extracted Fields")
        st.markdown("""
        - Vendor Name & Address
        - Invoice Number
        - Invoice Date & Due Date
        - Subtotal, Tax, Total
        - Line Items
        """)
    
    # Main content
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("📤 Upload Invoice")
        
        uploaded_file = st.file_uploader(
            "Choose an invoice image or PDF",
            type=["png", "jpg", "jpeg", "pdf", "tiff", "bmp"],
            help="Upload an invoice or receipt image"
        )
        
        if uploaded_file is not None:
            # Display uploaded image
            if uploaded_file.type.startswith("image"):
                image = Image.open(uploaded_file)
                st.image(image, caption="Uploaded Invoice", use_container_width=True)
            else:
                st.info(f"📄 Uploaded: {uploaded_file.name}")
            
            # Process button
            if st.button("🔍 Parse Invoice", type="primary", use_container_width=True):
                with st.spinner("Processing invoice..."):
                    try:
                        # Save temp file
                        temp_path = Path(f"./data/temp/{uploaded_file.name}")
                        temp_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        with open(temp_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        
                        # Load extractor and process
                        extractor = load_extractor(ocr_engine, languages, use_gpu)
                        result = cast(InvoiceData, extractor.extract(temp_path))
                        
                        # Store result in session state
                        st.session_state.result = result
                        st.session_state.success = True
                        
                        # Cleanup
                        temp_path.unlink(missing_ok=True)
                        
                    except Exception as e:
                        st.error(f"Error processing invoice: {str(e)}")
                        st.session_state.success = False
    
    with col2:
        st.header("📋 Extracted Data")
        
        if 'result' in st.session_state and st.session_state.get('success'):
            result: InvoiceData = st.session_state.result
            
            # Confidence score
            confidence = result.confidence_score * 100
            if confidence >= 70:
                st.success(f"✅ Confidence: {confidence:.1f}%")
            elif confidence >= 50:
                st.warning(f"⚠️ Confidence: {confidence:.1f}%")
            else:
                st.error(f"❌ Confidence: {confidence:.1f}%")
            
            # Key metrics
            metrics_col1, metrics_col2, metrics_col3 = st.columns(3)
            
            with metrics_col1:
                st.metric("Invoice #", result.invoice_number or "N/A")
            with metrics_col2:
                st.metric("Date", result.invoice_date or "N/A")
            with metrics_col3:
                total_str = f"{result.currency} {result.total:,.2f}" if result.total else "N/A"
                st.metric("Total", total_str)
            
            st.divider()
            
            # Tabs for different views
            tab1, tab2, tab3 = st.tabs(["📝 Details", "📦 Line Items", "🔤 Raw Text"])
            
            with tab1:
                # Vendor info
                st.subheader("🏢 Vendor Information")
                vendor_data = {
                    "Field": ["Name", "Address", "Tax ID"],
                    "Value": [
                        result.vendor_name or "—",
                        result.vendor_address or "—",
                        result.vendor_tax_id or "—"
                    ]
                }
                st.table(pd.DataFrame(vendor_data))
                
                # Invoice info
                st.subheader("📄 Invoice Details")
                invoice_data = {
                    "Field": ["Invoice Number", "Invoice Date", "Due Date"],
                    "Value": [
                        result.invoice_number or "—",
                        result.invoice_date or "—",
                        result.due_date or "—"
                    ]
                }
                st.table(pd.DataFrame(invoice_data))
                
                # Financial info
                st.subheader("💰 Financial Summary")
                financial_data = {
                    "Field": ["Subtotal", "Tax", "Discount", "Total"],
                    "Value": [
                        f"{result.currency} {result.subtotal:,.2f}" if result.subtotal else "—",
                        f"{result.currency} {result.tax_amount:,.2f}" if result.tax_amount else "—",
                        f"{result.currency} {result.discount:,.2f}" if result.discount else "—",
                        f"{result.currency} {result.total:,.2f}" if result.total else "—"
                    ]
                }
                st.table(pd.DataFrame(financial_data))
            
            with tab2:
                if result.line_items:
                    items_data = []
                    for item in result.line_items:
                        items_data.append({
                            "Description": item.description,
                            "Quantity": item.quantity or "—",
                            "Unit Price": f"{item.unit_price:,.2f}" if item.unit_price else "—",
                            "Amount": f"{item.amount:,.2f}" if item.amount else "—"
                        })
                    st.dataframe(pd.DataFrame(items_data), use_container_width=True)
                else:
                    st.info("No line items detected")
            
            with tab3:
                st.text_area("Raw OCR Text", result.raw_text, height=300)
            
            st.divider()
            
            # Export options
            st.subheader("📥 Export")
            export_col1, export_col2 = st.columns(2)
            
            with export_col1:
                json_data = result.to_json(indent=2)
                st.download_button(
                    label="📄 Download JSON",
                    data=json_data,
                    file_name="invoice_data.json",
                    mime="application/json",
                    use_container_width=True
                )
            
            with export_col2:
                # Convert to CSV-friendly format
                csv_data = pd.DataFrame([{
                    "vendor_name": result.vendor_name,
                    "invoice_number": result.invoice_number,
                    "invoice_date": result.invoice_date,
                    "due_date": result.due_date,
                    "subtotal": result.subtotal,
                    "tax": result.tax_amount,
                    "total": result.total,
                    "currency": result.currency,
                }])
                st.download_button(
                    label="📊 Download CSV",
                    data=csv_data.to_csv(index=False),
                    file_name="invoice_data.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        else:
            st.info("👆 Upload an invoice and click 'Parse Invoice' to see results")


if __name__ == "__main__":
    main()
