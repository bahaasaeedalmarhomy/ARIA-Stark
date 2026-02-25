import "@testing-library/jest-dom/vitest";

if (!window.matchMedia) {
    window.matchMedia = () =>
        ({
            matches: false,
            addEventListener: () => {},
            removeEventListener: () => {},
            addListener: () => {},
            removeListener: () => {},
            onchange: null,
            dispatchEvent: () => false,
            media: "",
        }) as unknown as MediaQueryList;
}

if (!("ResizeObserver" in window)) {
    class ResizeObserverMock {
        observe() {}
        unobserve() {}
        disconnect() {}
    }
    (window as unknown as { ResizeObserver: typeof ResizeObserver }).ResizeObserver =
        ResizeObserverMock as unknown as typeof ResizeObserver;
}
