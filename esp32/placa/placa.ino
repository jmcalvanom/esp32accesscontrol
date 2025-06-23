#include <Wire.h>
#include <PN532_I2C.h>
#include <NfcAdapter.h>
#include <LiquidCrystal_I2C.h>
#include <EthernetESP32.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

#define SDA_PIN 33
#define SCL_PIN 32

#define PIN_ZUMBADOR 4

PN532_I2C pn532_i2c(Wire);
NfcAdapter nfc = NfcAdapter(pn532_i2c);

LiquidCrystal_I2C lcd(0x27, 16, 2);

byte mac[] = { 0xDE, 0xAD, 0xBE, 0xEF, 0xFE, 0xEF };

IPAddress ip(192, 168, 5, 2);
IPAddress gateway(192, 168, 5, 1);
IPAddress subred(255, 255, 255, 252);

// URL del servidor central de gestion de accesos
const char *serverVerificar = "http://192.168.5.1:5000/verificar";
String uidString = "";

EMACDriver driver(ETH_PHY_LAN8720, 23, 18, 16);

//Funciones para construir los tonos del buzzer
void tonoOK() {
  tone(PIN_ZUMBADOR, 800);
  delay(500);
  noTone(PIN_ZUMBADOR);
}

void tonoKO() {
  tone(PIN_ZUMBADOR, 400);
  delay(250);
  noTone(PIN_ZUMBADOR);
  delay(250);
  tone(PIN_ZUMBADOR, 400);
  delay(250);
  noTone(PIN_ZUMBADOR);
}

//Funcion que emite la peticion de verificar al servidor
void verificar() {
  HTTPClient http;
  http.begin(serverVerificar);
  http.addHeader("Content-Type", "application/json");
  StaticJsonDocument<200> jsonDocument;
  jsonDocument["uid"] = uidString;

  String jsonString;
  serializeJson(jsonDocument, jsonString);

  Serial.println("Solicitando autorización: " + jsonString);
  lcd.setCursor(0, 1);
  lcd.print("                ");
  lcd.setCursor(0, 1);
  lcd.print("Conectando..");


  int httpCode = http.POST(jsonString);

  if (httpCode == HTTP_CODE_OK) {
    String payload = http.getString();
    Serial.println("Respuesta del servidor: " + payload);

    StaticJsonDocument<200> respuestaJson;
    deserializeJson(respuestaJson, payload);

    String acceso = respuestaJson["acceso"];

    if (acceso == "PERMITIDO") {
      lcd.setCursor(0, 1);
      lcd.print("                ");
      lcd.setCursor(3, 1);
      lcd.print("AUTORIZADA");
      Serial.println("Llave autorizada");
      tonoOK();
      delay(3000);
    } else if (acceso == "DENEGADO") {
      lcd.setCursor(0, 1);
      lcd.print("                ");
      lcd.setCursor(1, 1);
      lcd.print("NO AUTORIZADA");
      Serial.println("Llave denegada");
      tonoKO();
      delay(3000);
    } else {
      lcd.clear();
      lcd.setCursor(0, 1);
      lcd.print(" ERROR SERVIDOR");
      Serial.println("[API] Respuesta no esperada");
    }
  } else {
    lcd.clear();
    lcd.setCursor(0, 1);
    lcd.print(" ERROR SERVIDOR");
    Serial.println("Error en la solicitud HTTP");
  }

  http.end();
}

void setup() {
  Serial.begin(115200);
  delay(500);
  while (!Serial)
    ;

  Serial.println("Inicializando sistema...");

  pinMode(PIN_ZUMBADOR, OUTPUT);  // BUZZER

  Wire.begin(SDA_PIN, SCL_PIN);

  byte count = 0;
  for (byte address = 1; address < 127; address++) {
    Wire.beginTransmission(address);
    if (Wire.endTransmission() == 0) { 
      Serial.print("Dispositivo encontrado en 0x");
      Serial.println(address, HEX);
      count++;
    }
  }

  if (count == 0) {
    Serial.println("No se encontraron dispositivos I2C.");
  } else {
    Serial.print("Total de dispositivos encontrados: ");
    Serial.println(count);
  }

  Ethernet.init(driver);

  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("Iniciando...");
  lcd.setCursor(0, 1);
  lcd.print("Obteniendo IP...");

  if (Ethernet.begin() == 0) {
    Serial.println("No se pudo obtener IP mediante DHCP");
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print(" DHCP ERROR ");

    Ethernet.begin(mac, ip, gateway, subred);

    Serial.print("STATIC IP: ");
    Serial.println(Ethernet.localIP());

    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("IP:");
    lcd.setCursor(4, 0);
    lcd.print(Ethernet.localIP());
    delay(2000);
  } else {
    Serial.print("DHCP IP: ");
    Serial.println(Ethernet.localIP());
  }

  nfc.begin();
}

void loop() {
  Serial.println("***CONTROL DE ACCESO***");

  if (Ethernet.linkStatus() == LinkON) {

    lcd.setCursor(0, 1);
    lcd.print("Internet OK");

    Serial.println("NFC esperando...");

    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("*CONTROL ACCESO*");
    lcd.setCursor(0, 1);
    lcd.print("Acerque llave...");

    if (nfc.tagPresent()) {
      NfcTag tag = nfc.read();
      uidString = tag.getUidString();
      Serial.println("UID: " + uidString);
      lcd.clear();
      lcd.setCursor(0, 0);
      lcd.print("UID: " + uidString);

      Serial.println("Llave estandar, iniciando verificacion..");
      verificar();
    }
  } else {
    Serial.println("El ESP32 no dispone de conectividad");
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("    RJ45 KO     ");
    lcd.setCursor(0, 1);
    lcd.print("  NO INTERNET   ");
  }

  delay(1000);
}
