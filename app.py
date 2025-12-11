"""
Streamlit Shipment Management Application
Main application file with UI and business logic
"""

import streamlit as st
from PIL import Image
import pandas as pd
from datetime import datetime

# Import modules
from database import (
    init_database, save_shipment, update_shipment_status, update_shipment,
    get_all_shipments, get_shipment_by_qr_code, get_suppliers, get_audit_log,
    get_all_suppliers, add_supplier, update_supplier, delete_supplier,
    set_user_password, get_all_users
)
from qr_scanner import decode_qr_from_image, parse_qr_code
from auth import require_login, get_current_user, logout, is_admin
from config import STATUS_VALUES
from google_sheets import push_shipments_to_sheets, test_connection
from drive_upload import upload_file_to_drive
from telegram_notify import send_text, send_photo
from telegram_helpers import notify_shipment_if_received

# ----------------------- UI Helpers ----------------------- #
def inject_sidebar_styles():
    """Apply custom styles for a cleaner, more professional sidebar."""
    st.markdown(
        """
        <style>
        /* Sidebar container */
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #f7f9fc 0%, #eef2f7 100%);
            border-right: 1px solid #e5e7eb;
            padding-top: 12px;
        }
        /* Title and user info */
        [data-testid="stSidebar"] .sidebar-title {
            font-size: 20px;
            font-weight: 700;
            color: #111827;
            margin-bottom: 12px;
        }
        [data-testid="stSidebar"] .sidebar-user {
            font-size: 14px;
            color: #4b5563;
            margin-bottom: 6px;
        }
        [data-testid="stSidebar"] .sidebar-label {
            font-size: 13px;
            font-weight: 600;
            color: #111827;
            margin: 12px 0 6px 0;
        }
        /* Nav buttons - base */
        [data-testid="stSidebar"] .stButton>button {
            width: 100%;
            border: 1px solid #e5e7eb;
            background: #ffffff;
            color: #111827;
            border-radius: 10px;
            padding: 10px 12px;
            font-weight: 600;
            box-shadow: 0 1px 2px rgba(0,0,0,0.04);
            transition: all 0.15s ease;
        }
        /* Secondary (default) */
        [data-testid="stSidebar"] .stButton>button[data-testid="baseButton-secondary"] {
            background: #ffffff;
            color: #111827;
            border: 1px solid #e5e7eb;
        }
        [data-testid="stSidebar"] .stButton>button:hover {
            border-color: #3b82f6;
            box-shadow: 0 4px 10px rgba(59,130,246,0.16);
            transform: translateY(-1px);
        }
        /* Primary (selected) */
        [data-testid="stSidebar"] .stButton>button[data-testid="baseButton-primary"] {
            background: linear-gradient(135deg, #2563eb, #1d4ed8);
            color: #fff;
            border: 1px solid #1d4ed8;
            box-shadow: 0 6px 16px rgba(37,99,235,0.28);
        }
        [data-testid="stSidebar"] .stButton>button[data-testid="baseButton-primary"]:hover {
            filter: brightness(1.02);
            transform: translateY(-1px);
        }
        /* Logout button */
        [data-testid="stSidebar"] .logout-btn>button {
            width: 100%;
            border-radius: 8px;
            border: 1px solid #fca5a5;
            background: #fff1f2;
            color: #b91c1c;
            font-weight: 600;
        }
        [data-testid="stSidebar"] .logout-btn>button:hover {
            border-color: #ef4444;
            background: #ffe4e6;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def inject_main_styles():
    """Apply global spacing tweaks for better mobile experience."""
    st.markdown(
        """
        <style>
        /* Compact main padding for small screens */
        @media (max-width: 768px) {
            [data-testid="stAppViewContainer"] .main .block-container {
                padding-top: 1rem;
                padding-bottom: 2rem;
                padding-left: 0.9rem;
                padding-right: 0.9rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

# Function definitions
def scan_qr_screen():
    """Unified screen for scanning QR code - handles both new and existing shipments"""
    current_user = get_current_user()
    
    # Initialize session state for camera
    if 'show_camera' not in st.session_state:
        st.session_state['show_camera'] = False
    if 'scanned_qr_code' not in st.session_state:
        st.session_state['scanned_qr_code'] = None
    if 'found_shipment' not in st.session_state:
        st.session_state['found_shipment'] = None
    
    # Check if we have a found shipment to display
    found_shipment = st.session_state.get('found_shipment', None)
    scanned_qr_code = st.session_state.get('scanned_qr_code', None)
    
    # If we found a shipment, show it
    if found_shipment:
        show_shipment_info(current_user, found_shipment)
        return
    
    # If we have scanned QR code but no shipment found, show create form
    if scanned_qr_code and not found_shipment:
        scanned_data = st.session_state.get('scanned_qr_data', {})
        if scanned_data:
            show_create_shipment_form(current_user, scanned_data)
            return
    
    # Main layout
    st.subheader("Quét QR Code")
    
    # Button to start scanning
    col_btn1, col_btn2 = st.columns([1, 3])
    with col_btn1:
        if st.button("📷 Bắt đầu quét", type="primary", key="start_scan_btn"):
            st.session_state['show_camera'] = True
            st.session_state['scanned_qr_code'] = None
            st.session_state['found_shipment'] = None
            st.rerun()
    
    with col_btn2:
        if st.session_state['show_camera']:
            if st.button("❌ Dừng quét", key="stop_scan_btn"):
                st.session_state['show_camera'] = False
                st.rerun()
    
    # Show camera if enabled
    if st.session_state['show_camera']:
        st.info("Đưa QR code vào khung hình và chụp ảnh. Hệ thống sẽ tự động nhận diện.")
        
        picture = st.camera_input("📷 Quét mã QR", key="scan_camera")
        
        if picture is not None:
            # Show processing indicator
            with st.spinner("Đang xử lý và nhận diện QR code..."):
                try:
                    # Decode QR code automatically
                    image = Image.open(picture)
                    qr_text = decode_qr_from_image(image)
                except Exception as e:
                    st.error(f"❌ Lỗi khi xử lý ảnh: {str(e)}")
                    qr_text = None
                    # Check if pyzbar is available
                    try:
                        from qr_scanner import PYZBAR_AVAILABLE
                        if not PYZBAR_AVAILABLE:
                            st.error("**❌ Lỗi: Thư viện pyzbar chưa được cài đặt hoặc thiếu zbar DLL!**")
                            st.info("""
                            **Hướng dẫn cài đặt:**
                            1. Cài đặt pyzbar: `python -m pip install pyzbar`
                            2. Trên Windows, cần cài thêm zbar DLL:
                               - Tải từ: https://github.com/NuGet/Home/issues/3901
                               - Hoặc cài qua conda: `conda install -c conda-forge zbar`
                            3. Khởi động lại ứng dụng
                            """)
                    except:
                        pass
            
            if qr_text:
                # Parse QR code
                parsed_data = parse_qr_code(qr_text)
                
                if parsed_data:
                    qr_code = parsed_data.get('qr_code', '').strip()
                    
                    # Check if shipment already exists
                    existing_shipment = get_shipment_by_qr_code(qr_code) if qr_code else None
                    
                    if existing_shipment:
                        # Shipment exists - show info
                        st.session_state['found_shipment'] = existing_shipment
                        st.session_state['scanned_qr_code'] = qr_code
                        st.session_state['show_camera'] = False
                        st.rerun()
                    else:
                        # New shipment - show create form
                        st.success("✅ Đã nhận diện QR code! Đang chuyển sang form tạo phiếu...")
                        st.session_state['scanned_qr_data'] = parsed_data
                        st.session_state['scanned_qr_code'] = qr_code
                        st.session_state['show_camera'] = False
                        st.rerun()
            else:
                st.warning("⚠️ Không phát hiện QR code trong ảnh. Vui lòng thử lại.")
                
                # Check if OpenCV is available
                try:
                    from qr_scanner import CV2_AVAILABLE
                    if not CV2_AVAILABLE:
                        st.error("**❌ Lỗi: Thư viện opencv-python chưa được cài đặt!**")
                        st.info("""
                        **Hướng dẫn cài đặt:**
                        1. Cài đặt opencv-python: `python -m pip install opencv-python`
                        2. Khởi động lại ứng dụng
                        """)
                except:
                    pass
                
                st.info("**Mẹo để quét thành công:**")
                st.info("   - Đảm bảo QR code rõ ràng và đủ ánh sáng")
                st.info("   - Giữ camera ổn định, không bị mờ")
                st.info("   - QR code phải nằm hoàn toàn trong khung hình")
                st.info("   - Thử chụp lại với góc độ khác")
    else:
        st.info("Click nút 'Bắt đầu quét' để mở camera và quét QR code")


def show_shipment_info(current_user, shipment):
    """Show existing shipment information with option to mark as received"""
    st.subheader("📦 Thông Tin Phiếu Gửi Hàng")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.success("✅ Phiếu đã tồn tại trong hệ thống!")
        
        # Display full shipment information
        st.write("### Chi Tiết Phiếu")
        
        info_col1, info_col2 = st.columns(2)
        
        with info_col1:
            st.write(f"**Mã QR Code:** {shipment['qr_code']}")
            st.write(f"**IMEI:** {shipment['imei']}")
            st.write(f"**Tên thiết bị:** {shipment['device_name']}")
            st.write(f"**Dung lượng:** {shipment['capacity']}")
        
        with info_col2:
            st.write(f"**Nhà cung cấp:** {shipment['supplier']}")
            st.write(f"**Trạng thái:** {shipment['status']}")
            st.write(f"**Thời gian gửi:** {shipment['sent_time']}")
            if shipment['received_time']:
                st.write(f"**Thời gian nhận:** {shipment['received_time']}")
            st.write(f"**Người tạo:** {shipment['created_by']}")
            if shipment['updated_by']:
                st.write(f"**Người cập nhật:** {shipment['updated_by']}")
        
        if shipment['notes']:
            st.write(f"**Ghi chú:** {shipment['notes']}")
        
        # Button to scan again
        if st.button("🔄 Quét lại QR code", key="rescan_btn"):
            st.session_state['found_shipment'] = None
            st.session_state['scanned_qr_code'] = None
            st.session_state['show_camera'] = True
            st.rerun()
    
    with col2:
        st.subheader("Cập Nhật Trạng Thái")
        
        current_status = shipment['status']
        st.info(f"Trạng thái hiện tại: **{current_status}**")
        
        # Only show "Đã nhận" button if not yet received
        if current_status != 'Đã nhận':
            if st.button("✅ Đã Nhận", type="primary", key="mark_received_btn"):
                result = update_shipment_status(
                    qr_code=shipment['qr_code'],
                    new_status='Đã nhận',
                    updated_by=current_user,
                    notes=None
                )
                
                if result['success']:
                    st.success("✅ Đã cập nhật trạng thái thành: **Đã nhận**")
                    st.balloons()
                    # Notify Telegram
                    notify_shipment_if_received(shipment['id'], force=True)
                    # Refresh shipment data
                    st.session_state['found_shipment'] = get_shipment_by_qr_code(shipment['qr_code'])
                    st.rerun()
                else:
                    st.error(f"❌ {result['error']}")
        else:
            st.success("✅ Phiếu đã được tiếp nhận")
        
        # Option to change to other status
        new_status = st.selectbox(
            "Thay đổi trạng thái:",
            STATUS_VALUES,
            index=STATUS_VALUES.index(current_status) if current_status in STATUS_VALUES else 0,
            key="status_select"
        )
        
        notes = st.text_area("Ghi chú cập nhật:", key="update_notes")
        
        if st.button("🔄 Cập Nhật", key="update_status_btn"):
            if new_status != current_status:
                result = update_shipment_status(
                    qr_code=shipment['qr_code'],
                    new_status=new_status,
                    updated_by=current_user,
                    notes=notes if notes else None
                )
                
                if result['success']:
                    st.success(f"✅ Đã cập nhật trạng thái thành: **{new_status}**")
                    st.balloons()
                    # Notify Telegram if Đã nhận
                    if new_status == 'Đã nhận':
                        notify_shipment_if_received(shipment['id'], force=True)
                    # Refresh shipment data
                    st.session_state['found_shipment'] = get_shipment_by_qr_code(shipment['qr_code'])
                    st.rerun()
                else:
                    st.error(f"❌ {result['error']}")
            else:
                st.warning("⚠️ Vui lòng chọn trạng thái khác với trạng thái hiện tại!")


def show_create_shipment_form(current_user, scanned_data):
    """Show form to create shipment from scanned QR data"""
    st.subheader("📝 Tạo Phiếu Gửi Hàng")
    
    # Initialize form data in session state if not exists
    if 'form_qr_code' not in st.session_state:
        st.session_state['form_qr_code'] = scanned_data.get('qr_code', '')
    if 'form_imei' not in st.session_state:
        st.session_state['form_imei'] = scanned_data.get('imei', '')
    if 'form_device_name' not in st.session_state:
        st.session_state['form_device_name'] = scanned_data.get('device_name', '')
    if 'form_capacity' not in st.session_state:
        st.session_state['form_capacity'] = scanned_data.get('capacity', '')
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.success("✅ Đã quét QR code thành công!")
        st.write("**Vui lòng kiểm tra và điền đầy đủ thông tin:**")
        
        # Editable form fields
        qr_code = st.text_input(
            "Mã QR Code:",
            value=st.session_state['form_qr_code'],
            key="input_qr_code",
            help="Mã QR code từ phiếu"
        )
        st.session_state['form_qr_code'] = qr_code
        
        imei = st.text_input(
            "IMEI:",
            value=st.session_state['form_imei'],
            key="input_imei",
            help="IMEI của thiết bị"
        )
        st.session_state['form_imei'] = imei
        
        device_name = st.text_input(
            "Tên thiết bị:",
            value=st.session_state['form_device_name'],
            key="input_device_name",
            help="Tên thiết bị (ví dụ: iPhone 15 Pro Max)"
        )
        st.session_state['form_device_name'] = device_name
        
        capacity = st.text_input(
            "Dung lượng:",
            value=st.session_state['form_capacity'],
            key="input_capacity",
            help="Dung lượng lưu trữ (ví dụ: 128GB)"
        )
        st.session_state['form_capacity'] = capacity
        
        # Show which fields are empty
        empty_fields = []
        if not qr_code.strip():
            empty_fields.append("Mã QR Code")
        if not imei.strip():
            empty_fields.append("IMEI")
        if not device_name.strip():
            empty_fields.append("Tên thiết bị")
        if not capacity.strip():
            empty_fields.append("Dung lượng")
        
        if empty_fields:
            st.warning(f"⚠️ Các trường còn trống: {', '.join(empty_fields)}")
        
        # Button to scan again
        if st.button("🔄 Quét lại QR code", key="rescan_btn"):
            # Clear form data
            for key in ['form_qr_code', 'form_imei', 'form_device_name', 'form_capacity']:
                if key in st.session_state:
                    del st.session_state[key]
            st.session_state['scanned_qr_data'] = None
            st.session_state['qr_scanned_success'] = False
            st.session_state['show_camera_send'] = True
            st.rerun()
    
    with col2:
        st.subheader("Thông Tin Phiếu")
        
        # Get suppliers
        suppliers_df = get_suppliers()
        if suppliers_df.empty:
            st.error("❌ Chưa có nhà cung cấp trong hệ thống")
            return
        
        supplier = st.selectbox(
            "Nhà cung cấp gửi:",
            suppliers_df['name'].tolist(),
            key="supplier_select"
        )
        
        notes = st.text_area("Ghi chú:", key="notes_input")
        uploaded_image_create = st.file_uploader("Upload ảnh (tùy chọn)", type=["png", "jpg", "jpeg"], key="upload_image_create")
        
        if st.button("💾 Lưu Phiếu", type="primary", key="save_btn"):
            # Validate required fields
            if not qr_code.strip():
                st.error("❌ Vui lòng nhập Mã QR Code!")
            elif not imei.strip():
                st.error("❌ Vui lòng nhập IMEI!")
            elif not device_name.strip():
                st.error("❌ Vui lòng nhập Tên thiết bị!")
            elif not capacity.strip():
                st.error("❌ Vui lòng nhập Dung lượng!")
            else:
                image_url = None
                if uploaded_image_create is not None:
                    file_bytes = uploaded_image_create.getvalue()
                    mime = uploaded_image_create.type or "image/jpeg"
                    orig_name = uploaded_image_create.name or "image.jpg"
                    ext = ""
                    if "." in orig_name:
                        ext = orig_name.split(".")[-1]
                    if not ext:
                        ext = "jpg"
                    sanitized_qr = qr_code.strip().replace(" ", "_") or "qr_image"
                    drive_filename = f"{sanitized_qr}.{ext}"
                    upload_res = upload_file_to_drive(file_bytes, drive_filename, mime)
                    if upload_res['success']:
                        image_url = upload_res['url']
                    else:
                        st.error(f"❌ Upload ảnh thất bại: {upload_res['error']}")
                        st.stop()

                result = save_shipment(
                    qr_code=qr_code.strip(),
                    imei=imei.strip(),
                    device_name=device_name.strip(),
                    capacity=capacity.strip(),
                    supplier=supplier,
                    created_by=current_user,
                    notes=notes if notes else None,
                    image_url=image_url
                )
                
                if result['success']:
                    st.success(f"✅ Phiếu #{result['id']} đã được lưu thành công!")
                    st.balloons()
                    # Notify only if default status is already Đã nhận (unlikely); skip otherwise
                    if supplier and STATUS_VALUES and STATUS_VALUES[0] == 'Đã nhận':
                        notify_shipment_if_received(result['id'], force=True)
                    # Clear scanned data and form data
                    for key in ['scanned_qr_data', 'scanned_qr_code', 'show_camera', 
                               'form_qr_code', 'form_imei', 'form_device_name', 'form_capacity', 'found_shipment']:
                        if key in st.session_state:
                            del st.session_state[key]
                    # Clear form
                    st.rerun()
                else:
                    st.error(f"❌ {result['error']}")


def receive_shipment_screen():
    """Screen for scanning QR code to receive/update shipment"""
    current_user = get_current_user()
    
    # Initialize session state for camera
    if 'show_camera_receive' not in st.session_state:
        st.session_state['show_camera_receive'] = False
    if 'shipment_found' not in st.session_state:
        st.session_state['shipment_found'] = False
    
    # Get found shipment from session
    found_shipment = st.session_state.get('found_shipment', None)
    
    # If shipment already found, show update form directly
    if found_shipment and st.session_state.get('shipment_found', False):
        st.session_state['show_camera_receive'] = False
        show_update_shipment_form(current_user, found_shipment)
        return
    
    # Main layout
    st.subheader("Quét QR Code để Tiếp Nhận Hàng")
    
    # Button to start scanning
    col_btn1, col_btn2 = st.columns([1, 3])
    with col_btn1:
        if st.button("Bắt đầu quét", type="primary", key="start_scan_receive_btn"):
            st.session_state['show_camera_receive'] = True
            st.session_state['shipment_found'] = False
            st.rerun()
    
    with col_btn2:
        if st.session_state['show_camera_receive']:
            if st.button("Dừng quét", key="stop_scan_receive_btn"):
                st.session_state['show_camera_receive'] = False
                st.rerun()
    
    # Show camera if enabled
    if st.session_state['show_camera_receive']:
        st.info("Đưa QR code vào khung hình và chụp ảnh. Hệ thống sẽ tự động nhận diện.")
        
        picture = st.camera_input("Quét mã QR", key="receive_camera")
        
        if picture is not None:
            # Show processing indicator
            with st.spinner("Đang xử lý và nhận diện QR code..."):
                # Decode QR code automatically
                image = Image.open(picture)
                qr_text = decode_qr_from_image(image)
            
            if qr_text:
                # Parse QR code to get qr_code
                parsed_data = parse_qr_code(qr_text)
                
                if parsed_data:
                    qr_code = parsed_data['qr_code']
                    
                    # If qr_code is empty, try to use first part of the string
                    if not qr_code.strip() and qr_text:
                        # Try to use first value before comma as qr_code
                        qr_code = qr_text.split(',')[0].strip()
                    
                    if qr_code.strip():
                        # Find shipment in database
                        shipment_data = get_shipment_by_qr_code(qr_code)
                        
                        if shipment_data:
                            # Successfully found
                            st.success("Tìm thấy phiếu! Đang chuyển sang tab cập nhật...")
                            
                            # Store in session state
                            st.session_state['found_shipment'] = shipment_data
                            st.session_state['shipment_found'] = True
                            st.session_state['show_camera_receive'] = False
                            
                            # Auto switch to update form
                            st.rerun()
                        else:
                            st.error(f"Không tìm thấy phiếu với mã QR: `{qr_code}`")
                            st.info("Vui lòng kiểm tra lại mã QR hoặc thử lại.")
                            st.info("Click 'Dừng quét' để quay lại.")
                    else:
                        st.warning("⚠️ Không thể xác định mã QR từ dữ liệu quét được.")
                        st.info(f"Dữ liệu nhận được: `{qr_text}`")
                        st.info("Vui lòng thử lại hoặc click 'Dừng quét' để quay lại.")
            else:
                st.warning("⚠️ Không phát hiện QR code trong ảnh. Vui lòng thử lại.")
                st.info("**Mẹo để quét thành công:**")
                st.info("   - Đảm bảo QR code rõ ràng và đủ ánh sáng")
                st.info("   - Giữ camera ổn định, không bị mờ")
                st.info("   - QR code phải nằm hoàn toàn trong khung hình")
                st.info("   - Thử chụp lại với góc độ khác")
    else:
        # Show instruction when camera is off
        if not found_shipment:
            st.info("Click nút 'Bắt đầu quét' để mở camera và quét QR code")
        else:
            # Show form if shipment found
            show_update_shipment_form(current_user, found_shipment)


def show_update_shipment_form(current_user, found_shipment):
    """Show form to update shipment status"""
    st.subheader("Cập Nhật Trạng Thái Phiếu")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.success("Đã tìm thấy phiếu!")
        st.write("**Thông tin phiếu:**")
        
        info_col1, info_col2 = st.columns(2)
        with info_col1:
            st.write(f"**Mã QR:** {found_shipment['qr_code']}")
            st.write(f"**IMEI:** {found_shipment['imei']}")
            st.write(f"**Tên máy:** {found_shipment['device_name']}")
        with info_col2:
            st.write(f"**Dung lượng:** {found_shipment['capacity']}")
            st.write(f"**NCC:** {found_shipment['supplier']}")
            st.write(f"**Thời gian gửi:** {found_shipment['sent_time']}")
        
        # Button to scan again
        if st.button("🔄 Quét lại QR code", key="rescan_receive_btn"):
            st.session_state['found_shipment'] = None
            st.session_state['shipment_found'] = False
            st.session_state['show_camera_receive'] = True
            st.rerun()
    
    with col2:
        st.subheader("Cập Nhật Trạng Thái")
        
        current_status = found_shipment['status']
        st.info(f"Trạng thái hiện tại: **{current_status}**")
        
        new_status = st.selectbox(
            "Trạng thái mới:",
            STATUS_VALUES,
            index=STATUS_VALUES.index(current_status) if current_status in STATUS_VALUES else 0,
            key="status_select"
        )
        
        notes = st.text_area("Ghi chú cập nhật:", key="update_notes")
        
        if st.button("Cập Nhật", type="primary", key="update_btn"):
            if new_status != current_status:
                result = update_shipment_status(
                    qr_code=found_shipment['qr_code'],
                    new_status=new_status,
                    updated_by=current_user,
                    notes=notes if notes else None
                )
                
                if result['success']:
                    st.success(f"Đã cập nhật trạng thái thành: **{new_status}**")
                    st.balloons()
                    # Notify Telegram nếu đã nhận
                    if new_status == 'Đã nhận':
                        res = notify_shipment_if_received(found_shipment['id'], force=True)
                        if res and not res.get('success'):
                            st.warning(f"Không gửi được Telegram: {res.get('error')}")
                    # Clear found shipment
                    if 'found_shipment' in st.session_state:
                        del st.session_state['found_shipment']
                    if 'shipment_found' in st.session_state:
                        st.session_state['shipment_found'] = False
                    if 'show_camera_receive' in st.session_state:
                        st.session_state['show_camera_receive'] = False
                    st.rerun()
                else:
                    st.error(f"❌ {result['error']}")
            else:
                st.warning("⚠️ Vui lòng chọn trạng thái khác với trạng thái hiện tại!")


def show_dashboard():
    """Show dashboard with statistics and shipment list"""
    st.header("Dashboard Quản Lý")
    
    # Get all shipments
    df = get_all_shipments()
    
    if df.empty:
        st.info("Chưa có dữ liệu phiếu gửi hàng")
        return
    
    # Calculate metrics
    total = len(df)
    sending = len(df[df['status'] == 'Đang gửi'])
    received = len(df[df['status'] == 'Đã nhận'])
    error = len(df[df['status'].isin(['Hư hỏng', 'Mất'])])
    
    # 2x2 layout for better mobile readability
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Tổng Phiếu", total)
    with col2:
        st.metric("Đang Gửi", sending)
    col3, col4 = st.columns(2)
    with col3:
        st.metric("Đã Nhận", received)
    with col4:
        st.metric("Lỗi", error)
    
    st.divider()
    
    # Filters
    st.subheader("Lọc Dữ Liệu")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        filter_status = st.multiselect(
            "Trạng thái:",
            STATUS_VALUES,
            default=STATUS_VALUES
        )
    
    with col2:
        suppliers_list = df['supplier'].unique().tolist()
        filter_supplier = st.multiselect(
            "Nhà cung cấp:",
            suppliers_list,
            default=suppliers_list
        )
    
    with col3:
        # Date range filter (if needed)
        date_cols = df.select_dtypes(include=['datetime64']).columns.tolist()
        if 'sent_time' in df.columns:
            try:
                df['sent_time'] = pd.to_datetime(df['sent_time'])
                min_date = df['sent_time'].min().date()
                max_date = df['sent_time'].max().date()
                
                date_range = st.date_input(
                    "Khoảng thời gian:",
                    value=(min_date, max_date),
                    min_value=min_date,
                    max_value=max_date
                )
            except:
                date_range = None
        else:
            date_range = None
    
    # Apply filters
    filtered_df = df[
        (df['status'].isin(filter_status)) &
        (df['supplier'].isin(filter_supplier))
    ]
    
    # Apply date filter if available
    if date_range and len(date_range) == 2 and 'sent_time' in filtered_df.columns:
        try:
            filtered_df['sent_time'] = pd.to_datetime(filtered_df['sent_time'])
            filtered_df = filtered_df[
                (filtered_df['sent_time'].dt.date >= date_range[0]) &
                (filtered_df['sent_time'].dt.date <= date_range[1])
            ]
        except:
            pass
    
    # Display filtered data
    st.subheader("Danh Sách Phiếu")
    st.dataframe(
        filtered_df,
        use_container_width=True,
        height=420,
        hide_index=True
    )
    
    # Export and Google Sheets buttons
    col_export1, col_export2 = st.columns(2)
    
    with col_export1:
        csv = filtered_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="Tải Excel (CSV)",
            data=csv,
            file_name=f"shipments_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    
    with col_export2:
        st.write("")  # Spacing
        if st.button("☁️ Push lên Google Sheets", type="primary", key="push_to_sheets_dashboard"):
            with st.spinner("Đang push dữ liệu lên Google Sheets..."):
                result = push_shipments_to_sheets(filtered_df, append_mode=True)
                if result['success']:
                    st.success(f"✅ {result['message']}")
                    st.balloons()
                else:
                    st.error(f"❌ {result['message']}")


def show_audit_log():
    """Show audit log of all changes"""
    st.header("📋 Lịch Sử Thay Đổi")
    
    # Get audit log
    limit = st.slider("Số lượng bản ghi:", 10, 500, 100, 10)
    df = get_audit_log(limit=limit)
    
    if df.empty:
        st.info("📭 Chưa có lịch sử thay đổi")
        return
    
    # Display audit log
    st.dataframe(
        df,
        use_container_width=True,
        height=500,
        hide_index=True
    )
    
    # Export button
    csv = df.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="📥 Tải Excel (CSV)",
        data=csv,
        file_name=f"audit_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )


def show_manage_shipments():
    """Show screen to manage all shipments with edit functionality"""
    st.header("📋 Quản Lý Phiếu Gửi Hàng")
    current_user = get_current_user()
    
    # Get all shipments
    df = get_all_shipments()
    
    if df.empty:
        st.info("📭 Chưa có phiếu gửi hàng nào")
        return
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        filter_status = st.multiselect(
            "Lọc theo trạng thái:",
            STATUS_VALUES,
            default=STATUS_VALUES,
            key="manage_filter_status"
        )
    
    with col2:
        suppliers_list = df['supplier'].unique().tolist()
        filter_supplier = st.multiselect(
            "Lọc theo NCC:",
            suppliers_list,
            default=suppliers_list,
            key="manage_filter_supplier"
        )
    
    with col3:
        search_qr = st.text_input("Tìm kiếm theo mã QR:", key="search_qr")
    
    # Apply filters
    filtered_df = df[
        (df['status'].isin(filter_status)) &
        (df['supplier'].isin(filter_supplier))
    ]
    
    if search_qr:
        filtered_df = filtered_df[filtered_df['qr_code'].str.contains(search_qr, case=False, na=False)]
    
    # Push to Google Sheets button
    col_push1, col_push2 = st.columns([3, 1])
    with col_push1:
        st.write("")  # Spacing
    with col_push2:
        if st.button("☁️ Push lên Google Sheets", type="primary", key="push_to_sheets_manage"):
            with st.spinner("Đang push dữ liệu lên Google Sheets..."):
                result = push_shipments_to_sheets(filtered_df, append_mode=True)
                if result['success']:
                    st.success(f"✅ {result['message']}")
                    st.balloons()
                else:
                    st.error(f"❌ {result['message']}")
    
    # Display shipments
    st.subheader(f"Tổng số: {len(filtered_df)} phiếu")
    
    for idx, row in filtered_df.iterrows():
        with st.expander(f"{row['qr_code']} - {row['device_name']} ({row['status']})", expanded=False):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.write("**Thông tin phiếu:**")
                info_col1, info_col2 = st.columns(2)
                
                with info_col1:
                    st.write(f"**Mã QR:** {row['qr_code']}")
                    st.write(f"**IMEI:** {row['imei']}")
                    st.write(f"**Tên thiết bị:** {row['device_name']}")
                    st.write(f"**Dung lượng:** {row['capacity']}")
                
                with info_col2:
                    st.write(f"**NCC:** {row['supplier']}")
                    st.write(f"**Trạng thái:** {row['status']}")
                    st.write(f"**Thời gian gửi:** {row['sent_time']}")
                    if pd.notna(row['received_time']):
                        st.write(f"**Thời gian nhận:** {row['received_time']}")
                    st.write(f"**Người tạo:** {row['created_by']}")
                    if pd.notna(row['updated_by']):
                        st.write(f"**Người cập nhật:** {row['updated_by']}")
                
                if pd.notna(row['notes']) and row['notes']:
                    st.write(f"**Ghi chú:** {row['notes']}")
            
            with col2:
                # Image upload status
                if not row.get('image_url'):
                    st.markdown("<span style='color:#b91c1c;font-weight:600'>Chưa upload ảnh</span>", unsafe_allow_html=True)
                else:
                    st.markdown(f"[Xem ảnh]({row['image_url']})")

                edit_key = f'edit_shipment_{row["id"]}'
                is_editing = st.session_state.get(edit_key, False)
                
                if st.button("✏️ Chỉnh sửa" if not is_editing else "❌ Hủy", key=f"btn_edit_{row['id']}"):
                    st.session_state[edit_key] = not is_editing
                    st.rerun()
            
            # Edit form
            edit_key = f'edit_shipment_{row["id"]}'
            if st.session_state.get(edit_key, False):
                st.divider()
                st.write("### ✏️ Chỉnh Sửa Phiếu")
                
                with st.form(f"edit_shipment_form_{row['id']}"):
                    col_form1, col_form2 = st.columns(2)
                    
                    with col_form1:
                        edit_qr_code = st.text_input("Mã QR Code:", value=row['qr_code'], key=f"edit_qr_{row['id']}")
                        edit_imei = st.text_input("IMEI:", value=row['imei'], key=f"edit_imei_{row['id']}")
                        edit_device_name = st.text_input("Tên thiết bị:", value=row['device_name'], key=f"edit_device_{row['id']}")
                        edit_capacity = st.text_input("Dung lượng:", value=row['capacity'], key=f"edit_capacity_{row['id']}")
                    
                    with col_form2:
                        suppliers_df = get_suppliers()
                        current_supplier_idx = 0
                        if suppliers_df['name'].tolist():
                            try:
                                current_supplier_idx = suppliers_df['name'].tolist().index(row['supplier'])
                            except:
                                pass
                        
                        edit_supplier = st.selectbox(
                            "Nhà cung cấp:",
                            suppliers_df['name'].tolist(),
                            index=current_supplier_idx,
                            key=f"edit_supplier_{row['id']}"
                        )
                        
                        edit_status = st.selectbox(
                            "Trạng thái:",
                            STATUS_VALUES,
                            index=STATUS_VALUES.index(row['status']) if row['status'] in STATUS_VALUES else 0,
                            key=f"edit_status_{row['id']}"
                        )
                        
                        edit_notes = st.text_area("Ghi chú:", value=row['notes'] if pd.notna(row['notes']) else '', key=f"edit_notes_{row['id']}")
                        uploaded_image = st.file_uploader("Upload ảnh (tùy chọn)", type=["png", "jpg", "jpeg"], key=f"upload_image_{row['id']}")
                    
                    col_submit1, col_submit2 = st.columns(2)
                    with col_submit1:
                        if st.form_submit_button("💾 Lưu thay đổi", type="primary"):
                            current_user = get_current_user()

                            image_url = row.get('image_url')
                            if uploaded_image is not None:
                                file_bytes = uploaded_image.getvalue()
                                mime = uploaded_image.type or "image/jpeg"
                                # Đặt tên file theo Mã QR, giữ lại phần mở rộng nếu có
                                orig_name = uploaded_image.name or "image.jpg"
                                ext = ""
                                if "." in orig_name:
                                    ext = orig_name.split(".")[-1]
                                if not ext:
                                    ext = "jpg"
                                sanitized_qr = edit_qr_code.strip().replace(" ", "_") or "qr_image"
                                drive_filename = f"{sanitized_qr}.{ext}"
                                upload_res = upload_file_to_drive(file_bytes, drive_filename, mime)
                                if upload_res['success']:
                                    image_url = upload_res['url']
                                else:
                                    st.error(f"❌ Upload ảnh thất bại: {upload_res['error']}")
                                    st.stop()

                            result = update_shipment(
                                shipment_id=row['id'],
                                qr_code=edit_qr_code.strip(),
                                imei=edit_imei.strip(),
                                device_name=edit_device_name.strip(),
                                capacity=edit_capacity.strip(),
                                supplier=edit_supplier,
                                status=edit_status,
                                notes=edit_notes.strip() if edit_notes.strip() else None,
                                updated_by=current_user,
                                image_url=image_url
                            )
                            
                            if result['success']:
                                st.success("✅ Đã cập nhật thành công!")
                                # Notify Telegram if status is Đã nhận
                                updated = get_shipment_by_qr_code(edit_qr_code.strip())
                                if updated and updated.get('status') == 'Đã nhận':
                                    res = notify_shipment_if_received(
                                        updated['id'],
                                        force=not row.get('telegram_message_id'),
                                        is_update_image=(uploaded_image is not None)
                                    )
                                    if res and not res.get('success'):
                                        st.warning(f"Không gửi được Telegram: {res.get('error')}")
                                edit_key = f'edit_shipment_{row["id"]}'
                                if edit_key in st.session_state:
                                    del st.session_state[edit_key]
                                st.rerun()
                            else:
                                st.error(f"❌ {result['error']}")
                    
                    with col_submit2:
                        if st.form_submit_button("❌ Hủy"):
                            edit_key = f'edit_shipment_{row["id"]}'
                            if edit_key in st.session_state:
                                del st.session_state[edit_key]
                            st.rerun()
            
            st.divider()


def show_settings_screen():
    """Show settings screen for admin to manage suppliers"""
    if not is_admin():
        st.error("❌ Chỉ có quyền admin mới có thể truy cập trang này!")
        return
    
    st.header("⚙️ Cài Đặt - Quản Lý Nhà Cung Cấp")
    
    tab1, tab2, tab3, tab4 = st.tabs(["📋 Danh Sách NCC", "➕ Thêm NCC Mới", "☁️ Google Sheets", "🔑 Tài Khoản"])
    
    with tab1:
        show_suppliers_list()
    
    with tab2:
        show_add_supplier_form()
    
    with tab3:
        show_google_sheets_settings()

    with tab4:
        show_user_management()


def show_suppliers_list():
    """Show list of all suppliers with edit/delete options"""
    st.subheader("📋 Danh Sách Nhà Cung Cấp")
    
    # Get all suppliers
    df = get_all_suppliers()
    
    if df.empty:
        st.info("📭 Chưa có nhà cung cấp nào trong hệ thống")
        return
    
    # Display suppliers
    for idx, row in df.iterrows():
        with st.container():
            col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 1, 1])
            
            with col1:
                status_icon = "✅" if row['is_active'] else "❌"
                st.write(f"**{status_icon} {row['name']}**")
            
            with col2:
                st.write(f"📞 {row['contact'] or 'N/A'}")
            
            with col3:
                st.write(f"📍 {row['address'] or 'N/A'}")
            
            with col4:
                if st.button("✏️ Sửa", key=f"edit_{row['id']}"):
                    st.session_state[f'edit_supplier_{row["id"]}'] = True
                    st.rerun()
            
            with col5:
                if row['is_active']:
                    if st.button("🗑️ Xóa", key=f"delete_{row['id']}"):
                        result = delete_supplier(row['id'])
                        if result['success']:
                            st.success(f"✅ Đã xóa nhà cung cấp: {row['name']}")
                            st.rerun()
                        else:
                            st.error(f"❌ {result['error']}")
                else:
                    if st.button("♻️ Khôi phục", key=f"restore_{row['id']}"):
                        result = update_supplier(row['id'], is_active=True)
                        if result['success']:
                            st.success(f"✅ Đã khôi phục nhà cung cấp: {row['name']}")
                            st.rerun()
                        else:
                            st.error(f"❌ {result['error']}")
            
            # Edit form (if edit button clicked)
            if st.session_state.get(f'edit_supplier_{row["id"]}', False):
                with st.expander(f"✏️ Sửa thông tin: {row['name']}", expanded=True):
                    with st.form(f"edit_form_{row['id']}"):
                        new_name = st.text_input("Tên nhà cung cấp:", value=row['name'], key=f"edit_name_{row['id']}")
                        new_contact = st.text_input("Liên hệ:", value=row['contact'] or '', key=f"edit_contact_{row['id']}")
                        new_address = st.text_input("Địa chỉ:", value=row['address'] or '', key=f"edit_address_{row['id']}")
                        new_active = st.checkbox("Đang hoạt động", value=bool(row['is_active']), key=f"edit_active_{row['id']}")
                        
                        col_submit1, col_submit2 = st.columns(2)
                        with col_submit1:
                            if st.form_submit_button("💾 Lưu thay đổi", type="primary"):
                                result = update_supplier(
                                    row['id'],
                                    name=new_name.strip() if new_name.strip() else None,
                                    contact=new_contact.strip() if new_contact.strip() else None,
                                    address=new_address.strip() if new_address.strip() else None,
                                    is_active=new_active
                                )
                                if result['success']:
                                    st.success("✅ Đã cập nhật thành công!")
                                    st.session_state[f'edit_supplier_{row["id"]}'] = False
                                    st.rerun()
                                else:
                                    st.error(f"❌ {result['error']}")
                        
                        with col_submit2:
                            if st.form_submit_button("❌ Hủy"):
                                st.session_state[f'edit_supplier_{row["id"]}'] = False
                                st.rerun()
            
            st.divider()


def show_add_supplier_form():
    """Show form to add new supplier"""
    st.subheader("➕ Thêm Nhà Cung Cấp Mới")
    
    with st.form("add_supplier_form"):
        name = st.text_input("Tên nhà cung cấp *", help="Tên nhà cung cấp (bắt buộc)")
        contact = st.text_input("Liên hệ", help="Số điện thoại hoặc email")
        address = st.text_input("Địa chỉ", help="Địa chỉ nhà cung cấp")
        
        if st.form_submit_button("➕ Thêm Nhà Cung Cấp", type="primary"):
            if not name.strip():
                st.error("❌ Vui lòng nhập tên nhà cung cấp!")
            else:
                result = add_supplier(
                    name=name.strip(),
                    contact=contact.strip() if contact.strip() else None,
                    address=address.strip() if address.strip() else None
                )
                
                if result['success']:
                    st.success(f"✅ Đã thêm nhà cung cấp: {name} (ID: {result['id']})")
                    st.balloons()
                    st.rerun()
                else:
                    st.error(f"❌ {result['error']}")


def show_user_management():
    """Allow admin to create/update user passwords"""
    st.subheader("🔑 Quản Lý Tài Khoản")

    with st.form("user_form"):
        username = st.text_input("Tên đăng nhập *", help="Ví dụ: admin, user, staff")
        password = st.text_input("Mật khẩu mới *", type="password")
        confirm = st.text_input("Nhập lại mật khẩu *", type="password")
        is_admin_flag = st.checkbox("Cấp quyền admin", value=False)

        submitted = st.form_submit_button("💾 Lưu tài khoản", type="primary")
        if submitted:
            if not username.strip():
                st.error("❌ Vui lòng nhập tên đăng nhập")
            elif not password:
                st.error("❌ Vui lòng nhập mật khẩu")
            elif password != confirm:
                st.error("❌ Mật khẩu nhập lại không khớp")
            else:
                result = set_user_password(username.strip(), password, is_admin_flag)
                if result['success']:
                    st.success("✅ Đã lưu tài khoản thành công")
                else:
                    st.error(f"❌ {result['error']}")

    st.divider()
    st.subheader("📋 Danh sách tài khoản")
    users_df = get_all_users()
    if users_df.empty:
        st.info("📭 Chưa có tài khoản nào")
        return

    # Hide real password, show masked
    users_df = users_df.copy()
    users_df['password'] = users_df['password'].apply(lambda x: '******' if x else '')
    users_df['is_admin'] = users_df['is_admin'].apply(lambda x: "Admin" if x else "User")

    st.dataframe(
        users_df,
        use_container_width=True,
        hide_index=True
    )


def show_google_sheets_settings():
    """Show Google Sheets settings and test connection"""
    st.subheader("☁️ Cài Đặt Google Sheets")
    
    st.info("""
    **Hướng dẫn:**
    1. Đảm bảo file `service_account.json` đã được cấu hình đúng
    2. Google Sheet đã được chia sẻ với service account email
    3. Click nút "Kiểm tra kết nối" để test
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔍 Kiểm tra kết nối", type="primary", key="test_gs_connection"):
            with st.spinner("Đang kiểm tra kết nối Google Sheets..."):
                result = test_connection()
                if result['success']:
                    st.success(f"✅ {result['message']}")
                    if 'worksheet' in result:
                        st.info(f"📋 Worksheet: {result['worksheet']}")
                else:
                    st.error(f"❌ {result['message']}")
    
    with col2:
        st.write("")  # Spacing
    
    st.divider()
    
    # Push all data option
    st.subheader("📤 Push dữ liệu")
    
    col_push1, col_push2 = st.columns(2)
    
    with col_push1:
        push_mode = st.radio(
            "Chế độ push:",
            ["Thêm mới (Append)", "Thay thế toàn bộ (Replace)"],
            key="push_mode"
        )
    
    with col_push2:
        st.write("")  # Spacing
    
    if st.button("📤 Push tất cả dữ liệu lên Google Sheets", type="primary", key="push_all_data"):
        with st.spinner("Đang push tất cả dữ liệu lên Google Sheets..."):
            df = get_all_shipments()
            if df.empty:
                st.warning("⚠️ Không có dữ liệu để push")
            else:
                append_mode = (push_mode == "Thêm mới (Append)")
                result = push_shipments_to_sheets(df, append_mode=append_mode)
                if result['success']:
                    st.success(f"✅ {result['message']}")
                    st.balloons()
                else:
                    st.error(f"❌ {result['message']}")


# Page configuration
st.set_page_config(
    page_title="Quản Lý Giao Nhận",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply styles
inject_sidebar_styles()
inject_main_styles()

# Initialize database on startup
if 'db_initialized' not in st.session_state:
    init_database()
    st.session_state['db_initialized'] = True

# Authentication check
if not require_login():
    st.stop()

# Main layout
st.sidebar.markdown('<div class="sidebar-title">Quản Lý Giao Nhận</div>', unsafe_allow_html=True)

# User info and logout
current_user = get_current_user()
st.sidebar.markdown(f'<div class="sidebar-user">Người dùng: <strong>{current_user}</strong></div>', unsafe_allow_html=True)
if st.sidebar.button("Đăng xuất", key="logout_btn"):
    logout()
    st.rerun()

# Navigation - only show Settings for admin
nav_options = ["Quét QR", "Quản Lý Phiếu", "Dashboard", "Lịch Sử"]
if is_admin():
    nav_options.append("Cài Đặt")

# Box-style navigation buttons (no dropdown, no radio)
if 'nav' not in st.session_state:
    st.session_state['nav'] = nav_options[0]

st.sidebar.markdown("**Chọn chức năng:**")
for opt in nav_options:
    is_current = st.session_state['nav'] == opt
    btn = st.sidebar.button(
        opt,
        type="primary" if is_current else "secondary",
        use_container_width=True,
        key=f"nav_btn_{opt}"
    )
    if btn:
        st.session_state['nav'] = opt
        st.rerun()

selected = st.session_state['nav']

# Main content area
if selected == "Quét QR":
    scan_qr_screen()

elif selected == "Quản Lý Phiếu":
    show_manage_shipments()

elif selected == "Dashboard":
    show_dashboard()

elif selected == "Lịch Sử":
    show_audit_log()

elif selected == "Cài Đặt":
    show_settings_screen()
