int pin = 1;

void setup() {
  // put your setup code here, to run once:
  Serial.begin(115200);
}

char c;

void loop() {
  // put your main code here, to run repeatedly:
    int value=analogRead(pin);
    value = ((9*value)/10);
    Serial.print('z');
    Serial.println(value);
    //Serial.flush();
    delay(30);

}
