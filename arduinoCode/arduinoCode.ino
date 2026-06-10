#include <Servo.h>

Servo panServo;  // מנוע ציר X (ימינה/שמאלה)
Servo tiltServo; // מנוע ציר Y (למעלה/למטה)

const int panPin = 9;    // חוט הפיקוד של סרוו X
const int tiltPin = 10;  // חוט הפיקוד של סרוו Y
const int laserPin = 3;  // חוט ה-PWM של הלייזר (פין 3)

void setup() {
  // פתיחת ערוץ התקשורת הטורית במהירות 9600
  Serial.begin(9600);
  
  // חיבור מנועי הסרוו לפינים המוגדרים
  panServo.attach(panPin);
  tiltServo.attach(tiltPin);
  
  // הגדרת פין הלייזר כיציאה
  pinMode(laserPin, OUTPUT);
  
  // מצב התחלתי: מנועים במרכז (90 מעלות) ולייזר כבוי לחלוטין
  panServo.write(90);
  tiltServo.write(90);
  analogWrite(laserPin, 0);
  
  // הגדרת זמן המתנה מקסימלי לקריאת נתונים (מונע השהיות בלולאה)
  Serial.setTimeout(10);
}

void loop() {
  // בדיקה אם הגיעו נתונים חדשים מהמחשב דרך כבל ה-USB
  if (Serial.available() > 0) {
    
    // קריאת מחרוזת הפקודה המלאה עד לתו ירידת שורה (\n)
    String data = Serial.readStringUntil('\n');
    
    // חיפוש המיקום של אותיות המפתח במחרוזת (לדוגמה: X100Y90L1)
    int xIndex = data.indexOf('X');
    int yIndex = data.indexOf('Y');
    int lIndex = data.indexOf('L');
    
    // וידאו שכל שלושת הפרמטרים קיימים בהודעה שנתקבלה
    if (xIndex != -1 && yIndex != -1 && lIndex != -1) {
      
      // גזירת ערכי הזוויות ומצב הלייזר מתוך המחרוזת והמרתם למספרים
      int posX = data.substring(xIndex + 1, yIndex).toInt();
      int posY = data.substring(yIndex + 1, lIndex).toInt();
      int laserState = data.substring(lIndex + 1).toInt();
      
      // 1. עדכון זוויות הראייה של מנועי הסרוו
      panServo.write(posX);
      tiltServo.write(posY);
      
      // 2. קביעת מצב הלייזר
      if (laserState == 1) {
        // הפעלת הלייזר ב-50% עוצמה (127 מתוך מקסימום 255)
        analogWrite(laserPin, 180);
      } else {
        // כיבוי אקטיבי מוחלט (0V)
        analogWrite(laserPin, 0);
      }
      
      // שליחת אישור חזרה לפייתון שהפקודה עובדה בהצלחה
      Serial.println("OK");
    }
  }
}