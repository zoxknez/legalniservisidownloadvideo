import { useEonSlice, useHrtiSlice, useRtsSlice, useVoyoSlice } from "../../context/appStore";

/** Service login credentials shared across Settings and service tabs. */
export function useCredentials() {
  const voyo = useVoyoSlice();
  const hrti = useHrtiSlice();
  const rts = useRtsSlice();
  const eon = useEonSlice();

  return {
    voyoEmail: voyo.voyoEmail,
    setVoyoEmail: voyo.setVoyoEmail,
    voyoPassword: voyo.voyoPassword,
    setVoyoPassword: voyo.setVoyoPassword,
    showVoyoPass: voyo.showVoyoPass,
    setShowVoyoPass: voyo.setShowVoyoPass,
    hrtiEmail: hrti.hrtiEmail,
    setHrtiEmail: hrti.setHrtiEmail,
    hrtiPassword: hrti.hrtiPassword,
    setHrtiPassword: hrti.setHrtiPassword,
    showHrtiPass: hrti.showHrtiPass,
    setShowHrtiPass: hrti.setShowHrtiPass,
    rtsEmail: rts.rtsEmail,
    setRtsEmail: rts.setRtsEmail,
    rtsPassword: rts.rtsPassword,
    setRtsPassword: rts.setRtsPassword,
    showRtsPass: rts.showRtsPass,
    setShowRtsPass: rts.setShowRtsPass,
    eonUsername: eon.eonUsername,
    setEonUsername: eon.setEonUsername,
    eonPassword: eon.eonPassword,
    setEonPassword: eon.setEonPassword,
    eonSerial: eon.eonSerial,
    setEonSerial: eon.setEonSerial,
    eonNumber: eon.eonNumber,
    setEonNumber: eon.setEonNumber,
    showEonPass: eon.showEonPass,
    setShowEonPass: eon.setShowEonPass,
    eonStatus: eon.eonStatus,
  };
}

export type CredentialsSlice = ReturnType<typeof useCredentials>;
