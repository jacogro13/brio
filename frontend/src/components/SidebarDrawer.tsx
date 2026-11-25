import type { ReactNode } from "react";

interface Props {
  open: boolean;
  mobile: boolean;
  onClose: () => void;
  children: ReactNode;
}

/** The sidebar: a column on desktop, an overlay drawer with a backdrop on mobile. */
export function SidebarDrawer({ open, mobile, onClose, children }: Props) {
  return (
    <>
      {mobile && open && (
        <div
          onClick={onClose}
          style={{
            position: "absolute",
            inset: 0,
            background: "rgba(0,0,0,0.5)",
            zIndex: 99,
          }}
        />
      )}
      {open && (
        <div
          style={
            mobile
              ? {
                  position: "absolute",
                  top: 0,
                  left: 0,
                  height: "100%",
                  zIndex: 100,
                }
              : { flexShrink: 0 }
          }
        >
          {children}
        </div>
      )}
    </>
  );
}
