"use client";
import { useEffect } from "react";
import { getFirestore, doc, onSnapshot } from "firebase/firestore";
import { app } from "@/lib/firebase";
import { useARIAStore } from "@/lib/store/aria-store";
import type { FirestoreAuditStep } from "@/types/aria";

export function useFirestoreSession() {
  const sessionId = useARIAStore((state) => state.sessionId);

  useEffect(() => {
    if (!sessionId) return;

    const db = getFirestore(app);
    const sessionRef = doc(db, "sessions", sessionId);

    const unsubscribe = onSnapshot(
      sessionRef,
      (snapshot) => {
        if (!snapshot.exists()) return;
        const data = snapshot.data();
        const steps = (data.steps ?? []) as FirestoreAuditStep[];
        useARIAStore.setState({ auditLog: steps });
      },
      (error) => {
        console.warn("[useFirestoreSession] onSnapshot error:", error);
      }
    );

    return () => unsubscribe();
  }, [sessionId]);
}
