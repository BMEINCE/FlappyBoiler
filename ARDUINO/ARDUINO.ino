int pin = 1;

void setup() {
  // put your setup code here, to run once:
  Serial.begin(115200);
}

void loop() {
  // put your main code here, to run repeatedly:
    int value=analogRead(pin);
    if (value >= 1000){
      value = 999;
    }
    //value = (value*9)/10;
    Serial.print('z');
    Serial.println(value);
    Serial.flush();
    //delay(5);
  }
