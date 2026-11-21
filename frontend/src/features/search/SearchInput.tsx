import { LoaderCircleIcon, SearchIcon, XIcon } from "lucide-react";
import type { KeyboardEvent, Ref } from "react";

import { Kbd } from "@/components/ui/kbd";
import { copy } from "@/lib/copy";

interface SearchInputProps {
  value: string;
  onChange: (value: string) => void;
  isFetching: boolean;
  inputRef?: Ref<HTMLInputElement>;
  onArrowDown?: () => void;
}

/** 48 px search field with label, spinner, clear button and "/" hint (docs/06 section 6.2). */
export function SearchInput({
  value,
  onChange,
  isFetching,
  inputRef,
  onArrowDown,
}: SearchInputProps) {
  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Escape" && value) {
      event.preventDefault();
      onChange("");
    } else if (event.key === "ArrowDown" && onArrowDown) {
      event.preventDefault();
      onArrowDown();
    }
  };
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor="search-input" className="text-meta text-muted-foreground">
        {copy.search.inputLabel}
      </label>
      <div className="group/search relative flex h-12 items-center rounded-xl border border-input bg-card transition-colors focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/25">
        <SearchIcon
          aria-hidden
          className="pointer-events-none absolute left-3.5 size-4 text-muted-foreground"
        />
        <input
          id="search-input"
          ref={inputRef}
          type="search"
          autoComplete="off"
          spellCheck={false}
          maxLength={500}
          value={value}
          placeholder={copy.search.placeholder}
          onChange={(event) => {
            onChange(event.target.value);
          }}
          onKeyDown={onKeyDown}
          className="h-full min-w-0 flex-1 bg-transparent pr-24 pl-10 text-body outline-none placeholder:text-muted-foreground [&::-webkit-search-cancel-button]:hidden"
        />
        <div className="absolute right-2 flex items-center gap-1">
          {isFetching ? (
            <LoaderCircleIcon
              role="status"
              aria-label={copy.search.searching}
              className="size-4 animate-spin text-muted-foreground motion-reduce:animate-none"
            />
          ) : null}
          {value ? (
            <button
              type="button"
              onClick={() => {
                onChange("");
              }}
              aria-label={copy.search.clear}
              className="inline-flex size-8 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring"
            >
              <XIcon aria-hidden className="size-4" />
            </button>
          ) : (
            <Kbd className="mr-1.5 hidden md:inline-flex" aria-hidden>
              /
            </Kbd>
          )}
        </div>
      </div>
    </div>
  );
}
