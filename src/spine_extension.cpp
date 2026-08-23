#include <spine/Extension.h>

namespace spine {

SpineExtension *getDefaultExtension() {
    return new DefaultSpineExtension();
}

}  // namespace spine
