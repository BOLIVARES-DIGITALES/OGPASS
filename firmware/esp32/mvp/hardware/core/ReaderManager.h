#pragma once
#include "OgpassReader.h"

namespace ogpass {
// Optional I/O is intentionally absent from beginPrimary()/pollPrimary().
// The platform must schedule beginOptional()/pollOptional() on a separate task.
class ReaderManager {
    struct Slot { OgpassReader* reader=nullptr; Role role=Role::OPTIONAL; };
    Slot slots[8]{};
    size_t size=0;
    bool poll(Role role, Detection& event) {
        for(size_t i=0;i<size;i++) {
            auto& slot=slots[i];
            if(slot.role==role && slot.reader->health()==Health::CONNECTED &&
               (slot.reader->capabilities() & IDENTIFY) && slot.reader->detect() &&
               slot.reader->read(event)==Result::OK) return true;
        }
        return false;
    }
public:
    bool add(OgpassReader& reader, Role role) {
        for(size_t i=0;i<size;i++) if(slots[i].reader==&reader) return false;
        if(size==8) return false;
        slots[size].reader=&reader;slots[size].role=role;++size;return true;
    }
    void beginPrimary() {
        for(size_t i=0;i<size;i++) if(slots[i].role==Role::PRIMARY) slots[i].reader->begin();
    }
    void beginOptional() {
        for(size_t i=0;i<size;i++) if(slots[i].role!=Role::PRIMARY) slots[i].reader->begin();
    }
    bool pollPrimary(Detection& event) { return poll(Role::PRIMARY,event); }
    bool pollOptional(Detection& event) { return poll(Role::OPTIONAL,event); }
};
}
