"use client";
import { useEffect } from "react";
import { Capacitor } from "@capacitor/core";

export default function NativeAppRedirect() {
  useEffect(() => {
    if (Capacitor.isNativePlatform() && !window.location.pathname.startsWith("/workspace")) {
      window.location.replace("/workspace/");
    }
  }, []);
  return null;
}
