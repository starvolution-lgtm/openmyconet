ERC report (2026-10-21T19:00:49, Encoding UTF8)
Report includes: Errors, Warnings, Exclusions

***** Sheet /
[footprint_filter]: Assigned footprint doesn't match footprint filters
    ; warning (excluded)
    @(8.250 in, 4.000 in): Symbol Coaxial1 [Conn_Coaxial]
    BASED ON THE SNAPEDA ORIGINAL FOOTPRINTS, THEY GAVE US TO PINS ON SYMBOL, BUT THE FOOTPRINT HAS 4 PIN PADS, PIN 1 FOR INPUT, PIN 2 FOR GND, AND PIN 3 & 4 FOR THE HOLDER OF THE BNC. WE KEPT THE PIN 3 & 4 OF THE BNC NC AND ACT AS BNC HOLDER PADS
[lib_symbol_mismatch]: Symbol doesn't match copy in library
    ; warning (excluded)
    @(9.300 in, 12.400 in): Symbol U9 [TS5A3159DBVRG4]
    THE ORIGINAL SNAPEDA FOOTPRINT, DOESNT HAVE THE PIN 3 ON THE SYMBOL (NC) THAT ACTUALLY ACTS FOR THE SWITCH BETWEEN ANA_OUT AND EC
[footprint_filter]: Assigned footprint doesn't match footprint filters
    ; warning (excluded)
    @(12.250 in, 10.450 in): Symbol J7 [Conn_Coaxial_Small]
    BASED ON THE SNAPEDA ORIGINAL FOOTPRINTS, THEY GAVE US TO PINS ON SYMBOL, BUT THE FOOTPRINT HAS 4 PIN PADS, PIN 1 FOR INPUT, PIN 2 FOR GND, AND PIN 3 & 4 FOR THE HOLDER OF THE BNC. WE KEPT THE PIN 3 & 4 OF THE BNC NC AND ACT AS BNC HOLDER PADS
[lib_symbol_mismatch]: Symbol doesn't match copy in library
    ; warning (excluded)
    @(13.650 in, 10.450 in): Symbol U13 [OPA2320SAIDGSR]
    LEGACY PINS OF OPA IC FROM ULTRALIBRARIAN FOR BOTH SHDN PINS DETECTED AS UNSPECIFIED. WE CHANGED BOTH OF THE PINS INTO PASSIVE STATUE TO AVOID THE ERC ERRORS. DOESNT AFFECTED THE ELECTRICITY
[footprint_filter]: Assigned footprint doesn't match footprint filters
    ; warning (excluded)
    @(15.900 in, 9.300 in): Symbol J10 [Conn_Coaxial_Small]
    BASED ON THE SNAPEDA ORIGINAL FOOTPRINTS, THEY GAVE US TO PINS ON SYMBOL, BUT THE FOOTPRINT HAS 4 PIN PADS, PIN 1 FOR INPUT, PIN 2 FOR GND, AND PIN 3 & 4 FOR THE HOLDER OF THE BNC. WE KEPT THE PIN 3 & 4 OF THE BNC NC AND ACT AS BNC HOLDER PADS
[footprint_filter]: Assigned footprint doesn't match footprint filters
    ; warning (excluded)
    @(18.500 in, 7.900 in): Symbol SW3 [SW_Nidec_CAS-120A1]
    USED ORIGINAL SPDT SYMBOL FROM KICAD, BUT USED THE FOOTPRINT OF JS102011JCQN WITH SAME PINS IDENTICAL, DOESNT AFFECTED THE ELECTRICITY
[lib_symbol_mismatch]: Symbol doesn't match copy in library
    ; warning (excluded)
    @(19.900 in, 6.450 in): Symbol U18 [TPS22919DCKR]
    DUE THE CHANGES OF THE TPS2291 ON THE SD CARD SIDE. ALSO THE VOUT PIN OF THIS SYMBOL HAS CHANGED FROM OUTPUT POWER TO THE PASSIVE TO PASS ERC, DOESNT AFFECTED THE ELCTRICITY. AND THE MOISTURE VDD ALSO HAS CONNECTED TO THE PIN 1 OF THE TERMINAL MOISTURE (J9)
[footprint_filter]: Assigned footprint doesn't match footprint filters
    ; warning (excluded)
    @(12.900 in, 9.050 in): Symbol J3 [Conn_01x10_Pin]
    2X05 FOOTPRINT COST SMALLER SIZED AND SMALLER AREA COMPARED TO THE 1X10 FOOTPRINT
[lib_symbol_mismatch]: Symbol doesn't match copy in library
    ; warning (excluded)
    @(3.500 in, 5.100 in): Symbol U2 [TPS63020DSJT]
    CHANGED THE VOUT / VIN PINS INTO PASSIVE, TO PASS ERC CHECKER, DOESNT AFFECTED THE ELECTRICITY
[lib_symbol_mismatch]: Symbol doesn't match copy in library
    ; warning (excluded)
    @(7.800 in, 5.100 in): Symbol U3 [TPS63020DSJT]
    CHANGED THE VOUT / VIN PINS INTO PASSIVE, TO PASS ERC CHECKER, DOESNT AFFECTED THE ELECTRICITY
[lib_symbol_mismatch]: Symbol doesn't match copy in library
    ; warning (excluded)
    @(8.500 in, 4.950 in): Symbol U16 [SX1262IMLTRT]
    CHANGED THE VDD_IN / VBAT PINS INTO PASSIVE, TO PASS ERC CHECKER, DOESNT AFFECTED THE ELECTRICITY
[lib_symbol_mismatch]: Symbol doesn't match copy in library
    ; warning (excluded)
    @(8.900 in, 1.950 in): Symbol U17 [TPS22919DCKR]
    CHANGED THE POWER OUTPUT SPECIFIED OF VOUT TPS22919 PIN INTO PASSIVE TO PASS THE ERC VIOLATION, THIS PIN ATTACHED TO VDD OF SD CARD FOR LOAD SWITCH

***** Sheet /RESULT AND REVIEW/

***** Sheet /BLOCK_DIAGRAM/

***** Sheet /BLOCK_DIAGRAM/USB-C/

***** Sheet /BLOCK_DIAGRAM/REGULATOR/

***** Sheet /BLOCK_DIAGRAM/BATTERY/

***** Sheet /BLOCK_DIAGRAM/MCU/
[multiple_net_names]: More than one name given to this bus or net
    ; warning (excluded)
    @(12.400 in, 6.600 in): Symbol #PWR068 Pin 1 [Power input, Line]
    @(15.050 in, 7.700 in): Symbol U7 Hidden pin 10 [EXP, Power input, Line]
    EXP PIN ON THE IC SHALL  CONNECTED TO GND, SO THE IC COULD GET EASIER RETURN PATH TOWARDS GND'

***** Sheet /BLOCK_DIAGRAM/DIGI_&_ANA_SENSORS/

***** Sheet /BLOCK_DIAGRAM/LoRa/

***** Sheet /BLOCK_DIAGRAM/Storage Micro SD Card/

 ** ERC messages: 13  Errors 0  Warnings 13

 ** Ignored checks:
    - None
