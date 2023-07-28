#include <LiquidCrystal.h>

#include "WiFiS3.h"
#include "secrets.h"
#include "RCSwitch.h"

int keyIndex = 0;            // your network key index number (needed only for WEP)

int status = WL_IDLE_STATUS;
WiFiClient client;
char server[] = "52.47.203.135";
bool awaiting_http_response = false;
unsigned long last_request = 0;

// LCD and buttons
const int btnsPin  = A0;
LiquidCrystal lcd(D8, D9, D4, D5, D6, D7);;
bool update_lcd = true;
unsigned long last_lcd_update = 0;
bool sleep_mode = false;

enum {
  BUTTON_NONE,
  BUTTON_UP,
  BUTTON_DOWN,
  BUTTON_LEFT,
  BUTTON_RIGHT,
  BUTTON_SELECT,
};

// menus
enum {
  CONFIG_MENU_NONE,
  CONFIG_MENU_CHARGE_TIME,
  CONFIG_MENU_MAX_TIME,
  CONFIG_MENU_FORCED_CHARGE,
  CONFIG_CHARGE_PROFILE,
  CONFIG_MENU_LAST,
};

uint8_t current_config_menu = CONFIG_MENU_NONE;
uint8_t config_charge_time = 0;
uint8_t config_max_time = 0;
uint8_t config_force = 0;

// charge management
enum {
  CHARGE_INACTIVE,
  CHARGE_ACTIVE,
  CHARGE_PENDING,
  CHARGE_DONE
};

const unsigned long HOUR = 3600L * 1000L;
unsigned long charge_start_time = 0;
uint8_t current_charge_hour = 0;
uint8_t charge_command[48];
uint8_t charge_state = CHARGE_INACTIVE;
uint8_t prev_charge_state = CHARGE_INACTIVE;

RCSwitch mySwitch = RCSwitch();
#define SWITCH_ON 2390807552
#define SWITCH_OFF 2172703744

// Received 2172703744 / 32bit Protocol: 2 ON
// Received 2390807552 / 32bit Protocol: 2 OFF

void setup_wifi() {
  Serial.begin(9600);
  while (!Serial) {
    ; // wait for serial port to connect. Needed for native USB port only
  }

  // check for the WiFi module:
  if (WiFi.status() == WL_NO_MODULE) {
    lcd.clear();
    lcd.setCursor(0,0);
    lcd.print(F("wifi unavailable"));
    Serial.println("Communication with WiFi module failed!");
    while (true);
  }

  String fv = WiFi.firmwareVersion();
  if (fv < WIFI_FIRMWARE_LATEST_VERSION) {
    Serial.println("Please upgrade the firmware");
  }

  uint8_t tries = 0;
  while (status != WL_CONNECTED && tries<3) {
    Serial.print("Attempting to connect to SSID: ");
    Serial.println(ssid);
    // Connect to WPA/WPA2 network. Change this line if using open or WEP network:
    status = WiFi.begin(ssid, pass);
    lcd.clear();
    lcd.setCursor(0,0);
    lcd.print(F("connecting..."));
    ++tries;
    // wait 10 seconds for connection:
    //delay(10000);
  }

}

void setDefaultCommand() {
  uint8_t i = 0;
  for(; i < config_charge_time; ++i)
    charge_command[i] = 1;

  for(; i < sizeof(charge_command); ++i)
    charge_command[i] = 0;
}

void readCommand() {
  for(uint8_t i = 0; i < sizeof(charge_command); ++i)
    charge_command[i] = 0;

  uint32_t received_data_num = 0;
  bool body = false;

  char buf[4];
  for(uint8_t i = 0; i < sizeof(buf); ++i) {
    buf[i] = 0;
  }

  while (client.available()) {
    char c = client.read();
    Serial.print(c);

    for(uint8_t i = 0; i < sizeof(buf)-1; ++i) {
      buf[i] = buf[i+1];
    }
    buf[sizeof(buf)-1] = c;

    if (!body) {
      if (buf[0] == 13 && buf[1] == 10 && buf[2] == 13 && buf[3] == 10) {
        body = true;
      }
      continue;
    }
    
    charge_command[received_data_num] = c-'0';

    received_data_num++;
    if(received_data_num % sizeof(charge_command) == 0) { 
      break;
    }
  }
  if (received_data_num>0) {
    awaiting_http_response = false;
    update_lcd = true;
    return;
  }

  if (millis()-last_request>60L * 1000L) {
    awaiting_http_response = false;
  }
}


void httpQueryCommand() {
  /* -------------------------------------------------------------------------- */  
  // close any connection before send a new request.
  // This will free the socket on the NINA module
  client.stop();

  if (client.connect(server, 80)) {
    Serial.println("connecting...");
    char get[64];
    sprintf(
      get,
      "GET /command/?time=%d&max_time=%d HTTP/1.1",
      config_charge_time,
      max(config_max_time,config_charge_time)
    );
    client.println(get);
    client.println("Host: 52.47.203.135");
    client.println("User-Agent: ArduinoWiFi/1.1");
    client.println("Connection: close");
    client.println();
    last_request = millis();
    awaiting_http_response = true;
    delay(2000);
  } else {
    // if you couldn't make a connection:
    Serial.println("connection failed");
  }
}

void updateChargeState() {
  // forced mode is on
  if (config_force) {
    charge_state = CHARGE_ACTIVE;
    return;
  }

  // force mode off and no charge time left
  if (config_charge_time == 0) {
    charge_state = CHARGE_DONE;
    return;
  }

  uint8_t starting_hour = (millis()-charge_start_time)/HOUR;
  bool was_charging = charge_command[current_charge_hour] > 0;

  // an hour has just elasped
  if (starting_hour > current_charge_hour) {
    current_charge_hour = starting_hour;
    update_lcd = true;

    // if we have been charging, decrease remaining charge time
    if (was_charging) {
      if (config_charge_time == 1) {
        config_charge_time = 0;
        charge_state = CHARGE_DONE;
        return;
      }
      else {
        config_charge_time--;
        config_max_time--;
      }
    }
  }
  
  if (starting_hour>48) {
    charge_state = CHARGE_DONE;
    return;
  }

  if(charge_command[starting_hour] == 0) {
    charge_state = CHARGE_PENDING;
  }
  else {
    charge_state = CHARGE_ACTIVE;
  }
}

void updateConfig(byte btnStatus) {
  // navigate menus
  switch(btnStatus) {
    case BUTTON_LEFT:
      current_config_menu--;
      if (current_config_menu >= CONFIG_MENU_LAST) {
        current_config_menu = CONFIG_MENU_NONE;
      }
      break;
    case BUTTON_RIGHT:
      current_config_menu++;
      if (current_config_menu >= CONFIG_MENU_LAST) {
        current_config_menu = CONFIG_MENU_NONE;
      }
      break;
    default:
      break;
  }

  // update configuration
  switch (current_config_menu) {
    case CONFIG_MENU_CHARGE_TIME:
      if (btnStatus == BUTTON_UP && config_charge_time < 48) {
        config_charge_time++;
      }
      else if (btnStatus == BUTTON_DOWN && config_charge_time > 0) {
        config_charge_time--;
      }
      else if(btnStatus == BUTTON_SELECT) {
        httpQueryCommand();
        setDefaultCommand();
        charge_start_time = millis();
        current_charge_hour = 0;
      }
      break;

    case CONFIG_MENU_MAX_TIME:
      if (btnStatus == BUTTON_UP && config_max_time < 48) {
        config_max_time++;
      }
      else if (btnStatus == BUTTON_DOWN && config_max_time > 0) {
        config_max_time--;
      }
      else if(btnStatus == BUTTON_SELECT) {
        httpQueryCommand();
        setDefaultCommand();
        charge_start_time = millis();
        current_charge_hour = 0;
      }
      break;

    case CONFIG_MENU_FORCED_CHARGE:
      if (btnStatus == BUTTON_UP || btnStatus == BUTTON_DOWN) {
        config_force = 1-config_force;
      }
      break;

    default://case BUTTON_NONE:
      //lcd.print(F("       "));
      break;
  }
}

void updateLCD() {
  char buf[16];

  lcd.clear();
  switch (current_config_menu) {
    case CONFIG_MENU_NONE: {
      lcd.setCursor(0,0);
      if (charge_state == CHARGE_INACTIVE) {
        lcd.print(F("charge: inactive"));
      }
      else if (charge_state == CHARGE_ACTIVE) {
        lcd.print(F("charge: active"));
      }
      else if (charge_state == CHARGE_PENDING) {
        lcd.print(F("charge: pending"));
      }
      else if (charge_state == CHARGE_DONE) {
        lcd.print(F("charge: done"));
      }
      
      if (config_force || (charge_state != CHARGE_PENDING && charge_state != CHARGE_ACTIVE))
        break;
      
      lcd.setCursor(0,1);
      int8_t last_charge_hour = sizeof(charge_command)-1;
      for (; last_charge_hour >= 0; last_charge_hour--) {
        if(charge_command[last_charge_hour] == 1) {
          break;
        }
      }
      sprintf(buf, "%d hours left", last_charge_hour-current_charge_hour+1);
      lcd.print(buf);
      break;
    }
    case CONFIG_MENU_CHARGE_TIME:
      lcd.setCursor(0, 0);
      lcd.print(F("Charge time:"));

      lcd.setCursor(0, 1);
      sprintf(buf, "%d hours", config_charge_time);
      lcd.print(buf);

      break;
    case CONFIG_MENU_MAX_TIME:
      lcd.setCursor(0, 0);
      lcd.print(F("Max duration:"));

      lcd.setCursor(0, 1);
      sprintf(buf, "%d hours", config_max_time);
      lcd.print(buf);
      break;

    case CONFIG_MENU_FORCED_CHARGE:
      lcd.setCursor(0, 0);
      if (config_force == 0) {
        lcd.print(F("Forced mode off"));
      }
      else {
        lcd.print(F("Forced mode on"));
      }
      break;

    case CONFIG_CHARGE_PROFILE:
      lcd.setCursor(0, 0);
      lcd.print(F("0h       48h"));

      for (uint8_t i = 0; i < 12; ++i) {
        buf[i] = '0';
      }

      for(uint8_t i = 0; i < sizeof(charge_command); ++i) {
        uint8_t offset = i/4;
        buf[offset] += charge_command[i];
      }
      
      buf[12] = 0;
      lcd.setCursor(0, 1);
      lcd.print(buf);
      break;
  }
  update_lcd = false;
  last_lcd_update = millis();
}

void btnListener(byte btnStatus) { 
  switch (btnStatus) {
    case BUTTON_NONE:
      break;
    default:
      updateConfig(btnStatus);
      if (sleep_mode) {
        sleep_mode = false;
        pinMode(10, OUTPUT);
        digitalWrite(10, HIGH);        
      }
      update_lcd = true;
  }
}

byte getBtnPressed() {
  int btnsVal = analogRead(btnsPin);
  if (btnsVal < 50)
    return BUTTON_RIGHT;
  else if (btnsVal < 250)
    return BUTTON_UP;
  else if (btnsVal < 350)
    return BUTTON_DOWN;
  else if (btnsVal < 450)
    return BUTTON_LEFT;
  else if (btnsVal < 650)
    return BUTTON_SELECT;
  else
    return BUTTON_NONE;
}


void setup_lcd() {
  Serial.begin(9600);
  Serial.println(F("Initialize System"));
  //Init LCD16x2 Shield
  lcd.begin(16, 2);
  lcd.print(F("restarting"));
  delay(1000);
}



void setup() {
  for(uint8_t i = 0; i < sizeof(charge_command); ++i)
    charge_command[i] = 0;

  setup_lcd();
  setup_wifi();

  //mySwitch.enableReceive(D3);
  mySwitch.enableTransmit(D3);
  mySwitch.setProtocol(2);
}

void loop() {
  if (awaiting_http_response) {
    readCommand();
  }

  updateChargeState();

  if (prev_charge_state != charge_state) {
    prev_charge_state = charge_state;
    update_lcd = true;

    if (charge_state == CHARGE_ACTIVE) {
      mySwitch.send(SWITCH_ON, 32);
      delay(500);
      pinMode(D2, OUTPUT);
      digitalWrite(D2, HIGH);
    } else {
      mySwitch.send(SWITCH_OFF, 32);
      delay(500);
      pinMode(D2, OUTPUT);
      digitalWrite(D2, LOW);
    }
  }
  
  btnListener(getBtnPressed());

  if (update_lcd) {
    updateLCD();
  }
  if (millis() - last_lcd_update >= 30000L) {
    if(!sleep_mode) {
      sleep_mode = true;
      pinMode(10, OUTPUT);
      digitalWrite(10, LOW);
    }
  }
  delay(100);
}