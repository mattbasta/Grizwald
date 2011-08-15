import errorcount

def register(patterns):
    patterns.append(("/api/error_count", errorcount.ErrorCountHandler))
    return patterns

