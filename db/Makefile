CC      = cc
CFLAGS  = -O2 -Wall -Wextra -std=c11

# ── Data headers ─────────────────────────────────────────────────────────────
SOLAR_HEADERS_MODERN = solar/eclipse_times_modern.h \
                       solar/eclipse_info_modern.h  \
                       solar/saros_modern.h

SOLAR_HEADERS_ALL    = solar/eclipse_times_all.h \
                       solar/eclipse_info_all.h  \
                       solar/saros_all.h

LUNAR_HEADERS_MODERN = lunar/eclipse_times_modern.h \
                       lunar/eclipse_info_modern.h  \
                       lunar/saros_modern.h

LUNAR_HEADERS_ALL    = lunar/eclipse_times_all.h \
                       lunar/eclipse_info_all.h  \
                       lunar/saros_all.h

# ── Targets ───────────────────────────────────────────────────────────────────
all: test_saros_lib

# saros_lib test — uses modern (Saros 110-173) slice for both solar and lunar
SAROS_LIB_HEADERS = saros.h \
                    $(SOLAR_HEADERS_MODERN) \
                    $(LUNAR_HEADERS_MODERN)

test_saros_lib: test_saros_lib.c solar_impl.c lunar_impl.c $(SAROS_LIB_HEADERS)
	$(CC) $(CFLAGS) -o test_saros_lib \
	    test_saros_lib.c solar_impl.c lunar_impl.c

# "all" variant — uses full Saros 1-180 dataset
SAROS_LIB_HEADERS_ALL = saros.h \
                        $(SOLAR_HEADERS_ALL) \
                        $(LUNAR_HEADERS_ALL)

test_saros_lib_all: test_saros_lib.c $(SAROS_LIB_HEADERS_ALL)
	$(CC) $(CFLAGS) -DSAROS_USE_ALL -o test_saros_lib_all \
	    test_saros_lib.c \
	    solar_impl_all.c \
	    lunar_impl_all.c

# Convenience: build solar_impl_all.c / lunar_impl_all.c on the fly
solar_impl_all.c:
	printf '#define SAROS_IMPL_SOLAR\n#define SAROS_USE_ALL\n' > $@
	printf '#include "solar/eclipse_times_all.h"\n' >> $@
	printf '#include "solar/eclipse_info_all.h"\n'  >> $@
	printf '#include "solar/saros_all.h"\n'          >> $@
	printf '#include "saros.h"\n'                >> $@

lunar_impl_all.c:
	printf '#define SAROS_IMPL_LUNAR\n#define SAROS_USE_ALL\n' > $@
	printf '#include "lunar/eclipse_times_all.h"\n' >> $@
	printf '#include "lunar/eclipse_info_all.h"\n'  >> $@
	printf '#include "lunar/saros_all.h"\n'          >> $@
	printf '#include "saros.h"\n'                >> $@

clean:
	rm -f test_saros_lib test_saros_lib_all solar_impl_all.c lunar_impl_all.c

.PHONY: all clean
