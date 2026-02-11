CC      = cc
CFLAGS  = -O2 -Wall -Wextra -std=c11

all: test_db test_progmem

test_db: test_db.c eclipse_db.c eclipse_db.h
	$(CC) $(CFLAGS) -o test_db test_db.c eclipse_db.c

# Header-only: all data baked into the .h, no eclipse_db.c needed
PROGMEM_HEADERS = eclipse_db_progmem.h \
                  eclipse_times_modern.h eclipse_info_modern.h saros_modern.h \
                  eclipse_times_all.h    eclipse_info_all.h    saros_all.h
test_progmem: test_progmem.c $(PROGMEM_HEADERS)
	$(CC) $(CFLAGS) -o test_progmem test_progmem.c

clean:
	rm -f test_db test_progmem

.PHONY: all clean
