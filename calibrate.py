#calibrate.py
import cv2
import numpy as np

# פונקציית דמה שהסליידרים חייבים לקבל (לא עושה כלום)
def nothing(x):
    pass

cap = cv2.VideoCapture(1)

# יצירת חלון ייעודי לסליידרים
cv2.namedWindow("Trackbars")

# יצירת הסליידרים - ערכי המינימום (L) וערכי המקסימום (U)
# H (Hue) = 0-179
# S (Saturation) = 0-255
# V (Value) = 0-255
cv2.createTrackbar("L - H", "Trackbars", 0, 179, nothing)
cv2.createTrackbar("L - S", "Trackbars", 50, 255, nothing)
cv2.createTrackbar("L - V", "Trackbars", 50, 255, nothing)
cv2.createTrackbar("U - H", "Trackbars", 179, 179, nothing)
cv2.createTrackbar("U - S", "Trackbars", 255, 255, nothing)
cv2.createTrackbar("U - V", "Trackbars", 255, 255, nothing)

print("🎯 Play with the sliders until ONLY the balloon is white in the Mask window.")
print("Press 'q' to quit.")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # קריאת המיקום הנוכחי של כל סליידר
    l_h = cv2.getTrackbarPos("L - H", "Trackbars")
    l_s = cv2.getTrackbarPos("L - S", "Trackbars")
    l_v = cv2.getTrackbarPos("L - V", "Trackbars")
    u_h = cv2.getTrackbarPos("U - H", "Trackbars")
    u_s = cv2.getTrackbarPos("U - S", "Trackbars")
    u_v = cv2.getTrackbarPos("U - V", "Trackbars")

    # יצירת מערכים מהמספרים שבחרת
    lower_color = np.array([l_h, l_s, l_v])
    upper_color = np.array([u_h, u_s, u_v])

    # יצירת המסיכה
    mask = cv2.inRange(hsv, lower_color, upper_color)

    # חיתוך התמונה המקורית לפי המסיכה (כדי שתראה את הצבע האמיתי שנשאר)
    result = cv2.bitwise_and(frame, frame, mask=mask)

    # תצוגת החלונות
    cv2.imshow("Original", frame)
    cv2.imshow("Mask (Black & White)", mask)
    cv2.imshow("Result (Color)", result)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        # כשתלחץ q, התוכנית תדפיס לך את הערכים המדויקים כדי שתוכל להעתיק אותם
        print("\n=== COPY THESE VALUES TO YOUR MAIN CODE ===")
        print(f"lower_color = np.array([{l_h}, {l_s}, {l_v}])")
        print(f"upper_color = np.array([{u_h}, {u_s}, {u_v}])")
        print("===========================================\n")
        break

# שחרור המצלמה
cap.release()
# פקודת סגירת החלונות
cv2.destroyAllWindows()

# הוספת כמה פעימות המתנה ריקות שנותנות למערכת ההפעלה זמן לחסל את החלונות באמת
for _ in range(5):
    cv2.waitKey(1)