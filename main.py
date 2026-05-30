import cv2
import numpy as np

# פתיחת המצלמה
cap = cv2.VideoCapture(1)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # היפוך התמונה כמו מראה
    frame = cv2.flip(frame, 1)
    
    # מציאת אמצע המסך
    h, w, _ = frame.shape
    center_x, center_y = int(w/2), int(h/2)

    # המרה ל-HSV
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # === הערכים המדויקים שלך מהכיול ===
    lower_color = np.array([138, 0, 0])
    upper_color = np.array([179, 255, 255])
    
    # יצירת מסיכה אחת נקייה
    mask = cv2.inRange(hsv, lower_color, upper_color)

    # ניקוי רעשים
    mask = cv2.erode(mask, None, iterations=2)
    mask = cv2.dilate(mask, None, iterations=2)

    # מציאת קווי מתאר של הבלון
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if len(contours) > 0:
        # לוקחים את הכתם הכי גדול במסך (כדי להתעלם מרעשי רקע קטנים)
        c = max(contours, key=cv2.contourArea)
        
        # מסננים רק אם זה באמת משהו גדול מ-500 פיקסלים (כמו בלון)
        if cv2.contourArea(c) > 500:
            M = cv2.moments(c)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])

                # ציור המסגרת והנקודה על הבלון
                cv2.drawContours(frame, [c], -1, (0, 255, 0), 2) 
                cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1) 

                # חישוב הסטייה ממרכז המסך
                error_x = cx - center_x
                error_y = center_y - cy

                # הצגת הנתונים למעלה בצד שמאל
                cv2.putText(frame, f"Error X: {error_x}  Y: {error_y}", (20, 50), 
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)

    # כוונת קבועה באמצע המסך (לייזר)
    cv2.line(frame, (center_x - 15, center_y), (center_x + 15, center_y), (0, 255, 255), 2)
    cv2.line(frame, (center_x, center_y - 15), (center_x, center_y + 15), (0, 255, 255), 2)

    # תצוגה
    cv2.imshow("Targeting System", frame)
    cv2.imshow("PC Vision (Mask)", mask)

    # עצירה חלקה בלחיצה על 'q' כשחלון הוידאו בפוקוס
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# תהליך כיבוי נקי
cap.release()
cv2.destroyAllWindows()

# שחרור חלונות תקועים בזיכרון של מערכת ההפעלה
for _ in range(5):
    cv2.waitKey(1)