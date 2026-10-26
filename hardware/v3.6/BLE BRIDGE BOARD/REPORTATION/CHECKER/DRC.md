** Drc report for BLEBRIDGE_BOARD.kicad_pcb **
** Created on 2026-10-22T20:14:04 **
** Report includes: Warnings, Exclusions **

** Found 4 DRC violations **
[courtyards_overlap]: Courtyards overlap
    Local override; warning (excluded)
    @(131.2000 mm, 85.9400 mm): Footprint U6
    @(109.3000 mm, 81.0800 mm): Footprint S1
    THE FOOTPRINT OVERLAY TO MAKE SURE THE SWITCH IS OUT FROM THE PCB. SMALL COLLIDE TO THE ANTENNA KEEP-OUT AREA, DOESNT AFFECTED MUCH. WE ARE CONSIDER TO USE LORA COMMUNICATION INSTEAD WIFI/LTE
[lib_footprint_mismatch]: Footprint doesn't match copy in library
    Local override; warning (excluded)
    @(109.0800 mm, 124.0600 mm): Footprint U2
    THE ORIGINAL FOOTPRINT FROM SNAPEDA CONTAINS AMOUNTS OF VIAS, EVERY NUMBER ON THE PADS ITSELF DOESNT MATCHED THE SYMBOL. OUR ACTION HERE IS REMOVED THEM AND REPLACED WITH ONE VIAS ON THE MIDDLE OF THE PAD
[lib_footprint_mismatch]: Footprint doesn't match copy in library
    Local override; warning (excluded)
    @(109.9350 mm, 89.2800 mm): Footprint U5
    THE ORIGINAL FOOTPRINT FROM SNAPEDA HAS A TIGHT SOLDER MASK FORMAT, SO THAT WE ALLOWED SOLDER BRIDGED FOR EVERY PINS ON THE IC. DOESNT AFFECTED THE ELECTRICITY
[lib_footprint_mismatch]: Footprint doesn't match copy in library
    Local override; warning (excluded)
    @(173.3500 mm, 117.7000 mm): Footprint U3
    THE ORIGINAL FOOTPRINT FROM SNAPEDA CONTAINS AMOUNTS OF VIAS, EVERY NUMBER ON THE PADS ITSELF DOESNT MATCHED THE SYMBOL. OUR ACTION HERE IS REMOVED THEM AND REPLACED WITH ONE VIAS ON THE MIDDLE OF THE PAD

** Found 0 unconnected pads **

** Found 0 Footprint errors **

** Ignored checks **
    - Silkscreen clipped by board edge

** End of Report **
