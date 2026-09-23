import { completeCheckout } from "../checkout/complete-checkout";
import { updateDisplayName } from "../profile/update-profile";

export const routes = {
  "POST /checkout": completeCheckout,
  "POST /profile/display-name": updateDisplayName,
};
