"""Owner-selected Vietnam shadow identity; no transport or runtime dependencies."""

USER_AGENT = ("IndoPacificRecord-ShadowCollector/0.1 "
              "(+https://indopacificrecord.org; research archive; contact via site)")
# Recognise the new product and keep honouring legacy named refusals. Changing
# the transmitted identity must not become a way around a publisher's rules.
ROBOTS_TOKENS = ("indopacificrecord-shadowcollector", "indopacificrecord",
                 "chinamilwatch-shadowcollector", "chinamilwatch")
