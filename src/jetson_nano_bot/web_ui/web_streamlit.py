import streamlit as st
import cv2
import numpy as np
from PIL import Image
import io
import rospy
from geometry_msgs.msg import Point

# Khởi tạo ROS Node trong main thread
if "ros_initialized" not in st.session_state:
    rospy.init_node("streamlit_ros_publisher", anonymous=True, disable_signals=True)
    st.session_state["ros_initialized"] = True  # Đánh dấu đã khởi tạo ROS

# ROS Publisher
goal_pub = rospy.Publisher("/goal_point", Point, queue_size=10)

# Đọc file PGM
def load_pgm(pgm_path):
    image = cv2.imread(pgm_path, cv2.IMREAD_GRAYSCALE)
    return image

st.title("Bản đồ indoor")

# Đường dẫn file bản đồ
pgm_path = "./static/library.pgm"  # Thay bằng đường dẫn thực tế

# Hiển thị bản đồ
map_image = load_pgm(pgm_path)

if map_image is not None:
    # Chuyển ảnh thành PNG để hỗ trợ click
    img_pil = Image.fromarray(map_image)
    buf = io.BytesIO()
    img_pil.save(buf, format="PNG")
    byte_im = buf.getvalue()

    # Hiển thị ảnh bản đồ
    st.image(byte_im, caption="Click để chọn điểm đến", use_container_width=True)

    # Lấy tọa độ click
    query_params = st.query_params
    if "x" in query_params and "y" in query_params:
        x = int(query_params["x"])
        y = int(query_params["y"])
        st.write(f"**Tọa độ điểm đến: ({x}, {y})**")

        # Gửi tọa độ đến ROS khi click
        if st.button("Gửi tọa độ đến ROS"):
            goal_msg = Point()
            goal_msg.x = x
            goal_msg.y = y
            goal_msg.z = 0  # Không dùng trục Z

            goal_pub.publish(goal_msg)
            st.success("Đã gửi tọa độ đến ROS!")

else:
    st.error("Không thể tải bản đồ")
