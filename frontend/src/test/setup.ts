import "@testing-library/jest-dom/vitest";
import "fake-indexeddb/auto";
import { afterEach } from "vitest";

afterEach(() => {
  localStorage.clear();
  sessionStorage.clear();
});
