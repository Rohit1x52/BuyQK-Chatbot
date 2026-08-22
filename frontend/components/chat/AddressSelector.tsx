"use client";

import {
  FormEvent,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  createSavedAddress,
  getSavedAddresses,
} from "../../services/chat";

import { useChatStore } from "../../store/chatStore";

import type {
  Address,
  AddressSelectionMetadata,
} from "../../types/chat";


/* =========================================================
   Props
   ========================================================= */

interface AddressSelectorProps {
  metadata: AddressSelectionMetadata;
}


/* =========================================================
   Address Validation
   ========================================================= */

function isAddress(
  value: unknown
): value is Address {
  if (
    !value ||
    typeof value !== "object"
  ) {
    return false;
  }

  const item =
    value as Record<string, unknown>;

  return (
    typeof item.id === "number" &&
    Number.isInteger(item.id) &&
    item.id > 0 &&
    typeof item.label === "string" &&
    typeof item.address === "string"
  );
}


/* =========================================================
   Normalize Addresses
   ========================================================= */

function normalizeAddresses(
  addresses: unknown
): Address[] {
  if (!Array.isArray(addresses)) {
    return [];
  }

  /*
   * Remove malformed and duplicate addresses.
   *
   * The backend remains authoritative.
   * This only protects the UI from malformed metadata.
   */
  const valid =
    addresses.filter(isAddress);

  const seen =
    new Set<number>();

  return valid.filter(
    (address) => {
      if (seen.has(address.id)) {
        return false;
      }

      seen.add(address.id);

      return true;
    }
  );
}


/* =========================================================
   Address Selector
   ========================================================= */

export default function AddressSelector({
  metadata,
}: AddressSelectorProps) {

  /* =======================================================
     Zustand
     ======================================================= */

  const userId = useChatStore(
    (state) => state.userId
  );

  const continueWithSelectedAddress =
    useChatStore(
      (state) =>
        state.continueWithSelectedAddress
    );

  const isChatLoading = useChatStore(
    (state) => state.isLoading
  );


  /* =======================================================
     Backend Addresses
     ======================================================= */

  const initialAddresses = useMemo(
    () =>
      normalizeAddresses(
        metadata.addresses
      ),
    [metadata.addresses]
  );


  /* =======================================================
     Local UI State
     ======================================================= */

  const [
    addresses,
    setAddresses,
  ] = useState<Address[]>(
    initialAddresses
  );

  const [
    isRefreshing,
    setIsRefreshing,
  ] = useState(false);

  const [
    isCreating,
    setIsCreating,
  ] = useState(false);

  const [
    submittingAddressId,
    setSubmittingAddressId,
  ] = useState<number | null>(null);

  const [
    completed,
    setCompleted,
  ] = useState(false);

  const [
    showForm,
    setShowForm,
  ] = useState(
    Boolean(
      metadata.prefill &&
      initialAddresses.length === 0
    )
  );

  const [
    error,
    setError,
  ] = useState<string | null>(null);


  /* =======================================================
     New Address Form
     ======================================================= */

  const [
    label,
    setLabel,
  ] = useState("Home");

  const [
    addressLine,
    setAddressLine,
  ] = useState(
    metadata.prefill ?? ""
  );

  const [
    city,
    setCity,
  ] = useState("");

  const [
    stateName,
    setStateName,
  ] = useState("");

  const [
    postalCode,
    setPostalCode,
  ] = useState("");


  /* =======================================================
     Backend Capability
     ======================================================= */

  /*
   * The backend controls whether a new address may be
   * created during this flow.
   *
   * Missing allow_new remains backward-compatible.
   */
  const allowNew =
    metadata.allow_new !== false;


  /* =======================================================
     Busy State
     ======================================================= */

  const isBusy =
    isChatLoading ||
    isCreating ||
    submittingAddressId !== null;


  /* =======================================================
     Sync Backend Metadata
     ======================================================= */

  useEffect(() => {
    setAddresses(
      initialAddresses
    );
  }, [initialAddresses]);


  /* =======================================================
     Sync Prefilled Address
     ======================================================= */

  useEffect(() => {
    if (
      metadata.prefill &&
      !addressLine
    ) {
      setAddressLine(
        metadata.prefill
      );
    }
  }, [
    metadata.prefill,
    addressLine,
  ]);


  /* =======================================================
     Reset Completion State For New Metadata
     ======================================================= */

  useEffect(() => {
    setCompleted(false);
    setError(null);
  }, [
    metadata.addresses,
    metadata.prefill,
    metadata.allow_new,
  ]);


  /* =======================================================
     Load Saved Addresses
     ======================================================= */

  useEffect(() => {
    let cancelled = false;

    async function refreshAddresses() {

      if (userId === null) {
        return;
      }

      setIsRefreshing(true);

      try {
        const saved =
          await getSavedAddresses(
            userId
          );

        if (cancelled) {
          return;
        }

        const normalized =
          normalizeAddresses(
            saved
          );

        /*
         * Only replace the current list when the
         * backend request succeeds.
         */
        setAddresses(
          normalized
        );

        setError(null);

      } catch (refreshError) {

        if (cancelled) {
          return;
        }

        const message =
          refreshError instanceof Error
            ? refreshError.message
            : (
                "Unable to load your saved "
                + "addresses. Please try again."
              );

        setError(message);

      } finally {

        if (!cancelled) {
          setIsRefreshing(false);
        }
      }
    }

    void refreshAddresses();

    return () => {
      cancelled = true;
    };
  }, [userId]);


  /* =======================================================
     Continue With Existing Address
     ======================================================= */

  async function handleSelectAddress(
    addressId: number
  ) {

    /*
     * The frontend never changes checkout state itself.
     *
     * It only sends the selected address ID to the
     * backend through the chat store.
     *
     * Also verify that the ID belongs to an address currently
     * known to this selector. This is a UI integrity check only;
     * the backend remains authoritative.
     */
    const addressExists =
      addresses.some(
        (address) => address.id === addressId
      );

    if (
      isBusy ||
      !Number.isInteger(addressId) ||
      addressId <= 0 ||
      !addressExists
    ) {
      return;
    }

    setSubmittingAddressId(
      addressId
    );

    setError(null);

    try {

      const success =
        await continueWithSelectedAddress(
          addressId
        );

      /*
       * Only the backend/chat workflow can confirm that
       * selecting the address successfully advanced checkout.
       */
      if (success) {

        setCompleted(true);

      } else {

        setError(
          "Unable to continue with the selected "
          + "address. Please try again."
        );
      }

    } catch (selectionError) {

      const message =
        selectionError instanceof Error
          ? selectionError.message
          : (
              "Unable to select this address. "
              + "Please try again."
            );

      setError(message);

    } finally {

      setSubmittingAddressId(null);
    }
  }


  /* =======================================================
     Validate New Address
     ======================================================= */

  function validateAddressForm():
    string | null {

    if (!label.trim()) {
      return "Address label is required.";
    }

    if (!addressLine.trim()) {
      return "Full address is required.";
    }

    /*
     * Do not impose country-specific postal-code rules
     * in the frontend.
     *
     * Backend validation is authoritative.
     */
    if (
      postalCode.trim() &&
      postalCode.trim().length > 50
    ) {
      return "Postal code is too long.";
    }

    if (city.trim().length > 100) {
      return "City name is too long.";
    }

    if (stateName.trim().length > 100) {
      return "State name is too long.";
    }

    return null;
  }


  /* =======================================================
     Create New Address
     ======================================================= */

  async function handleCreateAddress(
    event: FormEvent<HTMLFormElement>
  ) {

    event.preventDefault();

    /*
     * The backend explicitly controls whether this
     * operation is available.
     */
    if (!allowNew) {
      setError(
        "Creating a new address is not available "
        + "for this checkout."
      );

      return;
    }

    if (
      isBusy ||
      userId === null
    ) {
      return;
    }

    const validationError =
      validateAddressForm();

    if (validationError) {
      setError(
        validationError
      );

      return;
    }

    setIsCreating(true);
    setError(null);

    try {

      /* ---------------------------------------------------
         Persist Address
         --------------------------------------------------- */

      const created =
        await createSavedAddress({
          user_id: userId,

          label:
            label.trim(),

          address:
            addressLine.trim(),

          city:
            city.trim() ||
            undefined,

          state:
            stateName.trim() ||
            undefined,

          postal_code:
            postalCode.trim() ||
            undefined,
        });


      /*
       * Only add a valid backend response to the local UI.
       */
      if (!isAddress(created)) {
        throw new Error(
          "The server returned an invalid address."
        );
      }


      /* ---------------------------------------------------
         Update Local Display
         --------------------------------------------------- */

      setAddresses(
        (current) => {

          const withoutDuplicate =
            current.filter(
              (item) =>
                item.id !== created.id
            );

          return [
            ...withoutDuplicate,
            created,
          ];
        }
      );


      /* ---------------------------------------------------
         Automatically Continue
         ---------------------------------------------------
         
         Saving an address does NOT itself mean checkout
         succeeded.
         
         The newly-created address must still be submitted
         through the normal authoritative checkout flow.
         --------------------------------------------------- */

      const success =
        await continueWithSelectedAddress(
          created.id
        );

      if (success) {

        setCompleted(true);

      } else {

        setError(
          "Address was saved, but we could not "
          + "continue the order. Please try again."
        );
      }

    } catch (createError) {

      const message =
        createError instanceof Error
          ? createError.message
          : (
              "Unable to save this address. "
              + "Please check the details and "
              + "try again."
            );

      setError(message);

    } finally {

      setIsCreating(false);
    }
  }


  /* =======================================================
     Completed State
     ======================================================= */

  if (completed) {

    return (
      <div
        className="address-selector-complete"
        aria-live="polite"
      >
        Address selected. Continuing your order...
      </div>
    );
  }


  /* =======================================================
     Render
     ======================================================= */

  return (

    <section
      className="address-selector"
      aria-label="Delivery address selection"
    >

      {/* =================================================
          Header
          ================================================= */}

      <div
        className="address-selector-header"
      >

        <h3>
          Choose delivery address
        </h3>

        {isRefreshing && (
          <span
            className="address-selector-status"
            aria-live="polite"
          >
            Refreshing...
          </span>
        )}

      </div>


      {/* =================================================
          Error
          ================================================= */}

      {error && (

        <div
          className="address-selector-error"
          role="alert"
        >
          {error}
        </div>

      )}


      {/* =================================================
          Saved Addresses
          ================================================= */}

      {addresses.length > 0 ? (

        <div
          className="address-list"
          role="list"
        >

          {addresses.map(
            (item) => {

              const isSubmitting =
                submittingAddressId ===
                item.id;

              return (

                <button
                  key={item.id}
                  type="button"
                  className="address-card"
                  onClick={() =>
                    void handleSelectAddress(
                      item.id
                    )
                  }
                  disabled={isBusy}
                  aria-disabled={isBusy}
                  aria-label={
                    `Select ${item.label} address`
                  }
                >

                  <div
                    className="address-card-label"
                  >
                    {item.label}
                  </div>

                  <div
                    className="address-card-line"
                  >
                    {item.address}
                  </div>

                  {(item.city ||
                    item.state ||
                    item.postal_code) && (

                    <div
                      className="address-card-meta"
                    >
                      {[
                        item.city,
                        item.state,
                        item.postal_code,
                      ]
                        .filter(Boolean)
                        .join(", ")}
                    </div>

                  )}

                  {isSubmitting && (

                    <div
                      className="address-card-loading"
                      aria-live="polite"
                    >
                      Selecting...
                    </div>

                  )}

                </button>
              );
            }
          )}

        </div>

      ) : (

        <div
          className="address-empty-state"
        >
          No saved addresses yet.
        </div>

      )}


      {/* =================================================
          Add New Address
          ================================================= */}

      {allowNew &&
        !showForm && (

          <button
            type="button"
            className="btn btn-outline address-add-button"
            onClick={() => {
              setError(null);
              setShowForm(true);
            }}
            disabled={isBusy}
          >
            + Add new address
          </button>

        )}


      {/* =================================================
          New Address Form
          ================================================= */}

      {allowNew &&
        showForm && (

          <form
            className="address-form"
            onSubmit={
              handleCreateAddress
            }
          >

            {/* ---------------------------------------------
                Label
                --------------------------------------------- */}

            <label
              className="address-field"
            >

              <span>
                Label
              </span>

              <input
                type="text"
                value={label}
                onChange={(event) =>
                  setLabel(
                    event.target.value
                  )
                }
                disabled={isBusy}
                required
                maxLength={50}
                placeholder="Home"
              />

            </label>


            {/* ---------------------------------------------
                Full Address
                --------------------------------------------- */}

            <label
              className="address-field"
            >

              <span>
                Full address
              </span>

              <textarea
                value={addressLine}
                onChange={(event) =>
                  setAddressLine(
                    event.target.value
                  )
                }
                disabled={isBusy}
                required
                rows={3}
                maxLength={500}
                placeholder="House number, street, area"
              />

            </label>


            {/* ---------------------------------------------
                City / State
                --------------------------------------------- */}

            <div
              className="address-form-grid"
            >

              <label
                className="address-field"
              >

                <span>
                  City
                </span>

                <input
                  type="text"
                  value={city}
                  onChange={(event) =>
                    setCity(
                      event.target.value
                    )
                  }
                  disabled={isBusy}
                  maxLength={100}
                  placeholder="City"
                />

              </label>


              <label
                className="address-field"
              >

                <span>
                  State
                </span>

                <input
                  type="text"
                  value={stateName}
                  onChange={(event) =>
                    setStateName(
                      event.target.value
                    )
                  }
                  disabled={isBusy}
                  maxLength={100}
                  placeholder="State"
                />

              </label>

            </div>


            {/* ---------------------------------------------
                Postal Code
                --------------------------------------------- */}

            <label
              className="address-field"
            >

              <span>
                PIN / Postal code
              </span>

              <input
                type="text"
                value={postalCode}
                onChange={(event) =>
                  setPostalCode(
                    event.target.value
                  )
                }
                disabled={isBusy}
                maxLength={50}
                placeholder="PIN code"
              />

            </label>


            {/* ---------------------------------------------
                Actions
                --------------------------------------------- */}

            <div
              className="address-form-actions"
            >

              <button
                type="submit"
                className="btn btn-primary"
                disabled={isBusy}
              >
                {isCreating
                  ? "Saving..."
                  : "Save and continue"}
              </button>


              <button
                type="button"
                className="btn btn-outline"
                onClick={() => {
                  setError(null);
                  setShowForm(false);
                }}
                disabled={isBusy}
              >
                Cancel
              </button>

            </div>

          </form>

        )}

    </section>
  );
}