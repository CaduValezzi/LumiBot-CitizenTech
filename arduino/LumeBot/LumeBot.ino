// Robô CitizenTech — versão Tinkercad Circuits
// Digite os comandos no Serial Monitor: OI, LUZ, LER, VARRER, ALERTA:1, ALERTA:0, VERDE:1, VERDE:0
#include <Servo.h>

const int PIN_LDR = A0;

const int PIN_R_EYE = 6;
const int PIN_L_EYE = 8;

const int PIN_ALERT_LED = 7;

const int PIN_SERVO = 9;

// Calibre com o comando LER (mexa no slider de luz do fotorresistor)
const int LIMIAR_ESCURO = 700;
const int LIMIAR_PENUMBRA = 500;

Servo servo;

int lerLDR() {
  long soma = 0;
  for (int i = 0; i < 10; i++) {
    soma += analogRead(PIN_LDR);
    delay(5);
  }
  return soma / 10;
}

void acenar() {
  digitalWrite(PIN_L_EYE, HIGH);

  servo.write(65);
  delay(350);
  servo.write(115);
  delay(350);

  for (int i = 0; i < 3; i++) {
    if (i % 2 ==  0){
      digitalWrite(PIN_ALERT_LED, HIGH);
      delay(400);
      digitalWrite(PIN_R_EYE, HIGH);
      delay(400);
      digitalWrite(PIN_L_EYE, LOW);
      delay(400);
    } else{
      digitalWrite(PIN_ALERT_LED, LOW);
      delay(400);
      digitalWrite(PIN_R_EYE, LOW);
      delay(400);
      digitalWrite(PIN_L_EYE, HIGH);
      delay(400);
    }
      
  }
  digitalWrite(PIN_ALERT_LED, LOW);
  digitalWrite(PIN_R_EYE, HIGH);
  digitalWrite(PIN_L_EYE, HIGH);
  servo.write(90);
}

void varrer() {
  for (int a = 20; a <= 160; a += 5) { servo.write(a); delay(20); }
  for (int a = 160; a >= 20; a -= 5) { servo.write(a); delay(20); }
  servo.write(90);
}

void piscarAlerta() {
  for (int i = 0; i < 6; i++) {
    digitalWrite(PIN_ALERT_LED, !digitalRead(PIN_ALERT_LED));
    delay(150);
  }
  digitalWrite(PIN_ALERT_LED, HIGH);
}
void piscarEsquerdo(){
   for (int i = 0; i < 3; i++) {
    digitalWrite(PIN_L_EYE, !digitalRead(PIN_L_EYE));
    delay(150);
  }
  digitalWrite(PIN_L_EYE, HIGH);
}
void piscarDireito(){
   for (int i = 0; i < 3; i++) {
    digitalWrite(PIN_R_EYE, !digitalRead(PIN_R_EYE));
    delay(150);
  }
  digitalWrite(PIN_R_EYE, HIGH);
}
void roboFeliz(){
   for (int i = 0; i < 3; i++) {
    bool proximo = !digitalRead(PIN_R_EYE);
    digitalWrite(PIN_R_EYE, proximo);
    digitalWrite(PIN_L_EYE, proximo);
    delay(150);
  }
  servo.write(30);  delay(400);
  servo.write(150); delay(400);
  digitalWrite(PIN_ALERT_LED, LOW);
  digitalWrite(PIN_R_EYE, HIGH);
  digitalWrite(PIN_L_EYE, HIGH);
  servo.write(90);
}

// Equivale a "como está a luz?": varre, lê, classifica e aciona o alerta
void verificarLuz() {
  varrer();
  int valor = lerLDR();
  Serial.print("LDR:");
  Serial.println(valor);

  if (valor >= LIMIAR_ESCURO) {
    Serial.println("NIVEL:insuficiente");
    piscarAlerta();
    piscarDireito();
  } else if (valor >= LIMIAR_PENUMBRA) {
    Serial.println("NIVEL:baixa");
    piscarAlerta();
    piscarEsquerdo();
  } else {
    Serial.println("NIVEL:adequada");
    roboFeliz();
  }
}

void processar(String cmd) {
  cmd.trim();
  cmd.toUpperCase();
  if (cmd.length() == 0) return;

  if (cmd == "OI") {
    acenar();
    Serial.println("OK");
  } else if (cmd == "LUZ") {
    verificarLuz();
  } else if (cmd == "LER") {
    Serial.print("LDR:");
    Serial.println(lerLDR());
  } else if (cmd == "VARRER") {
    varrer();
    Serial.println("OK");
  } else if (cmd == "ALERTA:1") {
    piscarAlerta();
    Serial.println("OK");
  } else if (cmd == "ALERTA:0") {
    digitalWrite(PIN_ALERT_LED, LOW);
    Serial.println("OK");
  } else if (cmd == "VERDE:1") {
    digitalWrite(PIN_L_EYE, HIGH);
    digitalWrite(PIN_R_EYE, HIGH);
    Serial.println("OK");
  } else if (cmd == "VERDE:0") {
    digitalWrite(PIN_L_EYE, LOW);
    digitalWrite(PIN_R_EYE, LOW);
    Serial.println("OK");
  } else if (cmd == "E:1") {
    digitalWrite(PIN_L_EYE, HIGH);
    Serial.println("OK");
  } else if (cmd == "E:0") {
    digitalWrite(PIN_L_EYE, LOW);
    Serial.println("OK");
  } else if (cmd == "D:1") {
    digitalWrite(PIN_R_EYE, HIGH);
    Serial.println("OK");
  } else if (cmd == "D:0") {
    digitalWrite(PIN_R_EYE, LOW);
    Serial.println("OK");
  } else {
    Serial.println("ERRO");
  }
}

void setup() {
  pinMode(PIN_ALERT_LED, OUTPUT);
  pinMode(PIN_L_EYE, OUTPUT);
  pinMode(PIN_R_EYE, OUTPUT);
  servo.attach(PIN_SERVO);
  servo.write(90);
  Serial.begin(9600);
  Serial.setTimeout(200);  // o Serial Monitor do Tinkercad não envia '\n'
  Serial.println("Robo pronto. Comandos: OI, LUZ, LER, VARRER");
}

void loop() {
  if (Serial.available()) {
    // retorna no '\n' (Python) ou após o timeout de 200 ms (Tinkercad)
    String cmd = Serial.readStringUntil('\n');
    processar(cmd);
  }
}
