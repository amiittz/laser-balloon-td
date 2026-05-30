import cv2
import numpy as np
import serial
import time

# === 1. הגדרת התקשורת לארדואינו ===
try:
    # מעודכן ל-COM5 עבור הארדואינו נאנו שלך
    arduino = serial.Serial('COM5', 9600, timeout=0.1)
    time.sleep(2) # המתנה לאתחול הארדואינו
    print("Arduino Connected Successfully on COM5!")
except:
    print("Warning: Arduino not found on COM5. Running in Video-only mode.")
    arduino = None

# === 2. פרמטרים פיזיים למיפוי (CALIBRATION) ===
# הגדר את שדה הראייה הטיפוסי של המצלמה שלך במעלות.
CAMERA_FOV_H = 65.0  # שדה ראייה אופקי
CAMERA_FOV_V = 48.0  # שדה ראייה אנכי

# זוויות הבסיס של המנועים כשהם מכוונים למרכז הפריים
SERVO_PAN_CENTER = 90
SERVO_TILT_CENTER = 90

# הגדרת משתני הסרוו
servo_pan = SERVO_PAN_CENTER
servo_tilt = SERVO_TILT_CENTER
laser_on = 0

# === 3. הגדרת המצלמה ===
cap = cv2.VideoCapture(0)

# נסיון להגדיר רזולוציה ספציפית כדי שהחישוב יהיה יציב
FRAME_W = 640
FRAME_H = 480
cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_W)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)

while True:
    ret, frame = cap.read()
    if not ret:
        break
        
    # היפוך התמונה כמו מראה
    frame = cv2.flip(frame, 1)
    
    # מידות הפריים המעשיות ואמצע המסך
    h, w, _ = frame.shape
    center_x, center_y = int(w/2), int(h/2)

    # === 4. עיבוד תמונה וזיהוי הבלון ===
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    
    # הערכים המדויקים מכיול הבלון האדום
    lower_color = np.array([138, 0, 0])
    upper_color = np.array([179, 255, 255])
    
    mask = cv2.inRange(hsv, lower_color, upper_color)
    mask = cv2.erode(mask, None, iterations=2)
    mask = cv2.dilate(mask, None, iterations=2)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if len(contours) > 0:
        c = max(contours, key=cv2.contourArea)
        
        if cv2.contourArea(c) > 500:
            M = cv2.moments(c)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])

                cv2.drawContours(frame, [c], -1, (0, 255, 0), 2) 
                cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1) 

                # חישוב הסטייה ממרכז המסך
                error_x = cx - center_x
                error_y = cy - center_y 

                # === 5. לוגיקת המיפוי (Targeting by Mapping) ===
                # המרת הסטייה בפיקסלים לסטייה פיזית במעלות
                offset_pan = -(error_x / w) * CAMERA_FOV_H
                offset_tilt = -(error_y / h) * CAMERA_FOV_V

                # חישוב הזוויות המוחלטות הרצויות
                raw_pan = SERVO_PAN_CENTER + offset_pan
                raw_tilt = SERVO_TILT_CENTER + offset_tilt

                # הגבלת הזוויות לטווח התקין של הסרוו (0-180)
                servo_pan = int(np.clip(raw_pan, 0, 180))
                servo_tilt = int(np.clip(raw_tilt, 0, 180))

                # === 6. לוגיקת הנעילה והלייזר ===
                if abs(offset_pan) < 1.5 and abs(offset_tilt) < 1.5:
                    laser_on = 1
                    cv2.putText(frame, "LOCKED ON! FIRING!", (20, 120), 
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)
                else:
                    laser_on = 0

                # הדפסת הנתונים על המסך
                cv2.putText(frame, f"Error (px): X:{error_x} Y:{error_y}", (20, 30), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
                cv2.putText(frame, f"Offset (deg): X:{offset_pan:.1f} Y:{offset_tilt:.1f}", (20, 60), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
                cv2.putText(frame, f"Servo (deg): X:{servo_pan} Y:{servo_tilt}", (20, 90), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)

    else:
        laser_on = 0

    # === 7. תקשורת לארדואינו ===
    if arduino:
        # שימוש במשתני המיפוי החדשים לפקודה
        command = f"X{servo_pan}Y{servo_tilt}L{laser_on}\n"
        arduino.write(command.encode('utf-8'))

    # ציור כוונת קבועה במרכז המסך
    cv2.line(frame, (center_x - 15, center_y), (center_x + 15, center_y), (0, 255, 255), 2)
    cv2.line(frame, (center_x, center_y - 15), (center_x, center_y + 15), (0, 255, 255), 2)

    cv2.imshow("Direct Mapping Targeting", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# === 8. סגירה נקייה של המערכת ===
if arduino:
    arduino.close()
cap.release()
cv2.destroyAllWindows()
for _ in range(5): cv2.waitKey(1)