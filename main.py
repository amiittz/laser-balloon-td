import sys
import cv2
import numpy as np
import serial
import time
import math
from PySide6.QtWidgets import QApplication, QMainWindow, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QWidget
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QImage, QPixmap


# trackbars need a callback, we don't actually use it
def nothing(x):
    pass


class LaserTrackerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Laser Tracker - Control Panel")
        self.resize(660, 580)

        # serial + state flags
        self.sending_enabled = False
        self.arduino = None
        self.init_serial()

        # camera field of view and servo neutral positions
        self.CAMERA_FOV_H = 65.0
        self.CAMERA_FOV_V = 48.0
        self.SERVO_PAN_CENTER = 90
        self.SERVO_TILT_CENTER = 90

        self.servo_pan = self.SERVO_PAN_CENTER
        self.servo_tilt = self.SERVO_TILT_CENTER
        self.laser_on = 0

        # HSV color range for the target - tweak these via the calibrate button
        self.lower_color = np.array([138, 0, 0])
        self.upper_color = np.array([179, 255, 255])
        self.calibrating = False

        # used to detect when we jumped to a different target
        self.first_detection_time = None
        self.prev_cx = None
        self.prev_cy = None
        self.TARGET_SWITCH_THRESHOLD = 50.0  # how many pixels counts as a "new" target

        self.init_ui()

        # camera index 1 (0 is usually the built-in webcam)
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

        self.btn_cal = QPushButton("Calibrate Color")
        self.btn_cal.setMinimumHeight(50)
        self.btn_cal.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold; font-size: 14px;")
        self.btn_cal.clicked.connect(self.toggle_calibration)

        self.btn_quit = QPushButton("Quit Application")
        self.btn_quit.setMinimumHeight(50)
        self.btn_quit.setStyleSheet("background-color: #555555; color: white; font-weight: bold; font-size: 14px;")
        self.btn_quit.clicked.connect(self.close)

        button_layout.addWidget(self.btn_tx)
        button_layout.addWidget(self.btn_cal)
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
            # send a reset so the servos recenter and the laser turns off when we stop
            if self.arduino:
                try:
                    self.arduino.write("X90Y90L0\n".encode('utf-8'))
                    self.arduino.flush()
                except Exception as e:
                    print(f"Warning: failed to send reset command: {e}")
            print(">>> Serial Transmission STOPPED <<<")

    def toggle_calibration(self):
        self.calibrating = not self.calibrating
        if self.calibrating:
            # spin up the trackbar window, seeded with whatever range we have now
            self.btn_cal.setText("Save & Close Calibration")
            self.btn_cal.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; font-size: 14px;")
            cv2.namedWindow("Trackbars")
            cv2.createTrackbar("L - H", "Trackbars", int(self.lower_color[0]), 179, nothing)
            cv2.createTrackbar("L - S", "Trackbars", int(self.lower_color[1]), 255, nothing)
            cv2.createTrackbar("L - V", "Trackbars", int(self.lower_color[2]), 255, nothing)
            cv2.createTrackbar("U - H", "Trackbars", int(self.upper_color[0]), 179, nothing)
            cv2.createTrackbar("U - S", "Trackbars", int(self.upper_color[1]), 255, nothing)
            cv2.createTrackbar("U - V", "Trackbars", int(self.upper_color[2]), 255, nothing)
            print("\nCalibration mode ON. Drag the sliders until only the target shows up white in the Mask window.")
        else:
            # done calibrating - the values are already live, just tear down the windows
            cv2.destroyWindow("Trackbars")
            cv2.destroyWindow("Mask (Calibration)")
            for _ in range(5):
                cv2.waitKey(1)
            self.btn_cal.setText("Calibrate Color")
            self.btn_cal.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold; font-size: 14px;")
            print("\n=== NEW COLOR VALUES SAVED TO MAIN ===")
            print(f"lower_color = np.array([{self.lower_color[0]}, {self.lower_color[1]}, {self.lower_color[2]}])")
            print(f"upper_color = np.array([{self.upper_color[0]}, {self.upper_color[1]}, {self.upper_color[2]}])")
            print("======================================\n")

    def update_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            return

        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape
        center_x, center_y = int(w / 2), int(h / 2)

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # while calibrating, pull the current slider values into our color range
        if self.calibrating:
            self.lower_color = np.array([
                cv2.getTrackbarPos("L - H", "Trackbars"),
                cv2.getTrackbarPos("L - S", "Trackbars"),
                cv2.getTrackbarPos("L - V", "Trackbars"),
            ])
            self.upper_color = np.array([
                cv2.getTrackbarPos("U - H", "Trackbars"),
                cv2.getTrackbarPos("U - S", "Trackbars"),
                cv2.getTrackbarPos("U - V", "Trackbars"),
            ])

        mask = cv2.inRange(hsv, self.lower_color, self.upper_color)
        # erode then dilate to kill the little speckles of noise
        mask = cv2.erode(mask, None, iterations=2)
        mask = cv2.dilate(mask, None, iterations=2)

        if self.calibrating:
            cv2.imshow("Mask (Calibration)", mask)
            cv2.waitKey(1)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        target_found_this_frame = False

        if len(contours) > 0:
            c = max(contours, key=cv2.contourArea)
            if cv2.contourArea(c) > 500:  # ignore anything too small to be the real target
                M = cv2.moments(c)
                if M["m00"] != 0:
                    target_found_this_frame = True
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])

                    # if the blob jumped a long way since last frame, assume it's a different target
                    if self.prev_cx is not None and self.prev_cy is not None:
                        distance_jump = math.hypot(cx - self.prev_cx, cy - self.prev_cy)
                        if distance_jump > self.TARGET_SWITCH_THRESHOLD:
                            # restart the lock timer so we don't fire on the wrong thing
                            self.first_detection_time = time.time()
                            print(f"\n[INFO] Target Switched! Jump distance: {distance_jump:.1f}px. Timer reset.")

                    self.prev_cx = cx
                    self.prev_cy = cy

                    cv2.drawContours(frame, [c], -1, (0, 255, 0), 2)
                    cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)

                    # how far off-center the target is, in pixels
                    error_x = cx - center_x
                    error_y = cy - center_y

                    # turn that pixel error into a servo angle offset via the FOV
                    offset_pan = (error_x / w) * self.CAMERA_FOV_H
                    offset_tilt = -(error_y / h) * self.CAMERA_FOV_V

                    raw_pan = self.SERVO_PAN_CENTER + offset_pan
                    raw_tilt = self.SERVO_TILT_CENTER + offset_tilt

                    # servos only go 0-180, so clamp it
                    self.servo_pan = int(np.clip(raw_pan, 0, 180))
                    self.servo_tilt = int(np.clip(raw_tilt, 0, 180))

                    # hold the target for a second before we actually fire
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
            # nothing worth tracking this frame, reset and stay safe
            self.first_detection_time = None
            self.prev_cx = None
            self.prev_cy = None
            self.laser_on = 0

        # build the command string and send it to the arduino
        command = f"X{self.servo_pan}Y{self.servo_tilt}L{self.laser_on}\n"

        status_prefix = "[TX ON] " if self.sending_enabled else "[TX OFF]"
        print(f"{status_prefix} {command.strip()}        ", end='\r')

        if self.arduino and self.sending_enabled:
            self.arduino.write(command.encode('utf-8'))

        # crosshair in the middle of the frame
        cv2.line(frame, (center_x - 15, center_y), (center_x + 15, center_y), (0, 255, 255), 2)
        cv2.line(frame, (center_x, center_y - 15), (center_x, center_y + 15), (0, 255, 255), 2)

        if self.sending_enabled:
            cv2.putText(frame, "TX: ON (Sending Data)", (10, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        else:
            cv2.putText(frame, "TX: OFF", (10, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        # hand the frame over to Qt for display
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h_img, w_img, ch = frame_rgb.shape
        bytes_per_line = ch * w_img

        q_img = QImage(frame_rgb.data, w_img, h_img, bytes_per_line, QImage.Format_RGB888)
        self.video_label.setPixmap(QPixmap.fromImage(q_img))

    def closeEvent(self, event):
        self.timer.stop()
        if self.arduino:
            # always send one final reset command, regardless of TX state
            try:
                self.arduino.write("X90Y90L0\n".encode('utf-8'))
                self.arduino.flush()
            except Exception as e:
                print(f"Warning: failed to send final reset command: {e}")
            self.arduino.close()
        self.cap.release()
        cv2.destroyAllWindows()
        for _ in range(5):
            cv2.waitKey(1)
        print("\nApplication closed gracefully.")
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = LaserTrackerApp()
    window.show()
    sys.exit(app.exec())
