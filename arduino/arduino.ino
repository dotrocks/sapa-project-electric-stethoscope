const int analogPin = A0; // Analog input pin that the sensor is attached to

// Define the starting and ending characters for the serial communication. 
// Sometimes python cannot read the serial data correctly. 
// To prevent this, we can use starting and ending characters.
const String startingChar = "S";
const String endingCar = "E";

void setup() {
  // Initialize serial communication at the 9600 baud rate
  Serial.begin(9600);

  // Configure the analog pin for input
  pinMode(analogPin, INPUT);
}

void loop() {
  // We want to sample the analog value at 8kHz (8000 times per second)
  // To achieve this, we need to read the analog value and wait for 125us
  int startedAt = micros();

  // Read the analog value
  int sensorValue = analogRead(analogPin);

  int endedAt = micros();
  int timeTook = endedAt - startedAt;

  // 125us = 8kHz sampling rate
  int timeRemaining = 125 - timeTook;

  // Send the sensor value to the serial port
  Serial.print(startingChar);
  Serial.print(sensorValue);
  Serial.println(endingCar);

  // Wait for the remaining time, this approach will give us 8kHz sampling rate in theory
  // But in practice, it may not be exactly 8kHz but it is good enough for our purposes
  if (timeRemaining > 0) {
    delayMicroseconds(timeRemaining);
  }
}
