import sys
import cv2
import numpy as np
import serial
import time
import math
from PySide6.QtWidgets import QApplication, QMainWindow, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QWidget
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QImage, QPixmap

class LaserTrackerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Laser Tracker - Control Panel")
        self.resize(660, 580)
        
        # === 1. הגדרת משתני מצב ותקשורת ===
        self.sending_enabled = False
        self.arduino = None
        self.init_serial()
        
        # פרמטרים פיזיים
        self.CAMERA_FOV_H = 65.0
        self.CAMERA_FOV_V = 48.0
        self.SERVO_PAN_CENTER = 90
        self.SERVO_TILT_CENTER = 90
        
        self.servo_pan = self.SERVO_PAN_CENTER
        self.servo_tilt = self.SERVO_TILT_CENTER
        self.laser_on = 0
        
        # משתני נעילה ועקיבה
        self.first_detection_time = None
        self.prev_cx = None
        self.prev_cy = None
        self.TARGET_SWITCH_THRESHOLD = 50.0 # מרחק בפיקסלים שמייצג "קפיצה" למטרה חדשה
        
        # === 2. בניית הממשק הגרפי ===
        self.init_ui()
        
        # === 3. הפעלת המצלמה והטיימר ===
        self.cap = cv2.VideoCapture(1)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30) 

    def init_serial(self):
        try:
            self.arduino = serial.Serial('COM5', 9600, timeout=0.1)
            print("Arduino Connected Successfully on COM5!")
        except:
            print("Warning: Arduino not found on COM5. Running in Video-only mode.")
            self.arduino = None

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        self.video_label = QLabel("Loading Camera...")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setMinimumSize(640, 480)
        self.video_label.setStyleSheet("background-color: black;")
        main_layout.addWidget(self.video_label)
        
        button_layout = QHBoxLayout()
        
        self.btn_tx = QPushButton("Start Transmission (TX: OFF)")
        self.btn_tx.setMinimumHeight(50)
        self.btn_tx.setStyleSheet("background-color: #f44336; color: white; font-weight: bold; font-size: 14px;")
        self.btn_tx.clicked.connect(self.toggle_tx)
        
        self.btn_quit = QPushButton("Quit Application")
        self.btn_quit.setMinimumHeight(50)
        self.btn_quit.setStyleSheet("background-color: #555555; color: white; font-weight: bold; font-size: 14px;")
        self.btn_quit.clicked.connect(self.close)
        
        button_layout.addWidget(self.btn_tx)
        button_layout.addWidget(self.btn_quit)
        
        main_layout.addLayout(button_layout)

    def toggle_tx(self):
        self.sending_enabled = not self.sending_enabled
        print("\n") 
        if self.sending_enabled:
            self.btn_tx.setText("Stop Transmission (TX: ON)")
            self.btn_tx.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; font-size: 14px;")
            print(">>> Serial Transmission STARTED <<<")
        else:
            self.btn_tx.setText("Start Transmission (TX: OFF)")
            self.btn_tx.setStyleSheet("background-color: #f44336; color: white; font-weight: bold; font-size: 14px;")
            print(">>> Serial Transmission STOPPED <<<")

    def update_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            return
            
        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape
        center_x, center_y = int(w/2), int(h/2)

        # === 4. עיבוד תמונה וזיהוי המטרה ===
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        lower_color = np.array([138, 0, 0])
        upper_color = np.array([179, 255, 255])
        
        mask = cv2.inRange(hsv, lower_color, upper_color)
        mask = cv2.erode(mask, None, iterations=2)
        mask = cv2.dilate(mask, None, iterations=2)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        target_found_this_frame = False

        if len(contours) > 0:
            c = max(contours, key=cv2.contourArea)
            if cv2.contourArea(c) > 500:
                M = cv2.moments(c)
                if M["m00"] != 0:
                    target_found_this_frame = True
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])

                    # בדיקת קפיצת מטרה (Target Switch)
                    if self.prev_cx is not None and self.prev_cy is not None:
                        # חישוב המרחק שהמטרה זזה מהפריים הקודם
                        distance_jump = math.hypot(cx - self.prev_cx, cy - self.prev_cy)
                        if distance_jump > self.TARGET_SWITCH_THRESHOLD:
                            # המטרה קפצה רחוק מדי - מאפסים את הטיימר!
                            self.first_detection_time = time.time()
                            print(f"\n[INFO] Target Switched! Jump distance: {distance_jump:.1f}px. Timer reset.")

                    # שמירת המיקום לפריים הבא
                    self.prev_cx = cx
                    self.prev_cy = cy

                    cv2.drawContours(frame, [c], -1, (0, 255, 0), 2) 
                    cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1) 

                    error_x = cx - center_x
                    error_y = cy - center_y 

                    offset_pan = -(error_x / w) * self.CAMERA_FOV_H
                    offset_tilt = -(error_y / h) * self.CAMERA_FOV_V

                    raw_pan = self.SERVO_PAN_CENTER + offset_pan
                    raw_tilt = self.SERVO_TILT_CENTER + offset_tilt

                    self.servo_pan = int(np.clip(raw_pan, 0, 180))
                    self.servo_tilt = int(np.clip(raw_tilt, 0, 180))

                    # === 5. לוגיקת הנעילה ===
                    if self.first_detection_time is None:
                        self.first_detection_time = time.time()

                    elapsed_time = time.time() - self.first_detection_time

                    if elapsed_time >= 1.0:
                        self.laser_on = 1
                        cv2.putText(frame, "LOCKED ON! FIRING!", (20, 150), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
                    else:
                        self.laser_on = 0
                        cv2.putText(frame, f"ACQUIRING... {1.0 - elapsed_time:.1f}s", (20, 150), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 165, 255), 3)

                    cv2.putText(frame, f"Error (px): X:{error_x} Y:{error_y}", (20, 30), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
                    cv2.putText(frame, f"Servo (deg): X:{self.servo_pan} Y:{self.servo_tilt}", (20, 60), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)

        if not target_found_this_frame:
            # אם לא נמצאה מטרה ראויה בפריים הזה, מאפסים הכל
            self.first_detection_time = None
            self.prev_cx = None
            self.prev_cy = None
            self.laser_on = 0

        # === 6. תקשורת והדפסה לטרמינל ===
        command = f"X{self.servo_pan}Y{self.servo_tilt}L{self.laser_on}\n"
        
        status_prefix = "[TX ON] " if self.sending_enabled else "[TX OFF]"
        print(f"{status_prefix} {command.strip()}        ", end='\r')
        
        if self.arduino and self.sending_enabled:
            self.arduino.write(command.encode('utf-8'))

        # === 7. ציורי מסך אחרונים והצגה ===
        cv2.line(frame, (center_x - 15, center_y), (center_x + 15, center_y), (0, 255, 255), 2)
        cv2.line(frame, (center_x, center_y - 15), (center_x, center_y + 15), (0, 255, 255), 2)

        if self.sending_enabled:
            cv2.putText(frame, "TX: ON (Sending Data)", (10, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        else:
            cv2.putText(frame, "TX: OFF", (10, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h_img, w_img, ch = frame_rgb.shape
        bytes_per_line = ch * w_img
        
        q_img = QImage(frame_rgb.data, w_img, h_img, bytes_per_line, QImage.Format_RGB888)
        self.video_label.setPixmap(QPixmap.fromImage(q_img))

    def closeEvent(self, event):
        self.timer.stop()
        if self.arduino:
            self.arduino.close()
        self.cap.release()
        print("\nApplication closed gracefully.")
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = LaserTrackerApp()
    window.show()
    sys.exit(app.exec())