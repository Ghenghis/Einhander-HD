"""Fresh matched-facade pass through the existing private no-fire route."""
import build_facade_ab_candidates as builder
import build_h24_matched_facade as matched
import run_h24_full_flypast as route

route.VARIANT = matched.VARIANT
route.DIRECTORY = matched.DIRECTORY
builder.check = matched.check

if __name__ == "__main__":
    route.run()
