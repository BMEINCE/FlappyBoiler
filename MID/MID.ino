//Small test program to check whether the "compression" of the data values during transmission could cause them to be inaccurate
int pin = 1;

void setup() {
  // put your setup code here, to run once:
  Serial.begin(115200);
}

char c;

void loop() {
  // put your main code here, to run repeatedly:
    int i;
    int temp;
    int total = 0;
    int adjustedtotal = 0;
    Serial.println("data:");
    for (i=0; i<50; i++){
      temp = analogRead(pin);
      Serial.print(temp);
      Serial.print("    ");
      total+= temp;
      temp = (temp*9)/10;
      temp = (temp*10)/9;
      Serial.println(temp);
      adjustedtotal+=temp;
    }
    total = total/50;
    adjustedtotal = adjustedtotal/50;
    Serial.println("Averages");
    Serial.println(total);
    Serial.println(adjustedtotal);
    Serial.println("\n\n\n\n");
    delay(5000);
}
