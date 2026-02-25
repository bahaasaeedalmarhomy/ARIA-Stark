"use client";

import { useEffect } from "react";
import { auth } from "@/lib/firebase";
import { signInAnonymously, onAuthStateChanged } from "firebase/auth";
import { useARIAStore } from "@/lib/store/aria-store";

/**
 * FirebaseAuthProvider — mounts invisibly in layout.tsx to silently authenticate
 * the user with Firebase Anonymous Auth on first page load (and across reloads,
 * since Firebase persists the anonymous session via browserLocalPersistence).
 *
 * Pattern: onAuthStateChanged handles both:
 *  - Existing anonymous user (page reload) → gets idToken immediately
 *  - No user yet → calls signInAnonymously → triggers onAuthStateChanged again
 *
 * Does NOT block rendering — UI renders optimistically; components that need
 * idToken guard themselves by checking `idToken === null`.
 */
export function FirebaseAuthProvider() {
    useEffect(() => {
        const unsubscribe = onAuthStateChanged(auth, async (user) => {
            if (user) {
                const token = await user.getIdToken();
                useARIAStore.setState({ uid: user.uid, idToken: token });
            } else {
                // No existing session — trigger anonymous sign-in.
                // This will fire onAuthStateChanged again with the new user.
                signInAnonymously(auth).catch((err) => {
                    console.error("[FirebaseAuthProvider] signInAnonymously failed:", err);
                });
            }
        });

        return () => unsubscribe();
    }, []);

    // Renders nothing — purely a side-effect provider
    return null;
}
