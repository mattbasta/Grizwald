import annotate
import errorcount


def register(patterns):
    patterns.append(("/api/error_count", errorcount.ErrorCountHandler))
    patterns.append(("/api/annotate", annotate.AnnotationHandler))
    return patterns

