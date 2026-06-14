import { beforeEach, describe, expect, it, vi } from "vitest";
import { ValidationError } from "../errors/data-error";
import { DATAClient } from "./base";
import { createHttpClientWithSpies } from "../../tests/test-utils";

describe("DATAClient base", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("getRoot calls root endpoint", async () => {
    const { client, request } = createHttpClientWithSpies();
    const data = new DATAClient(client);

    await data.getRoot();

    expect(request).toHaveBeenCalledWith({
      method: "GET",
      path: "/",
    });
  });

  it("getApplicationParameters includes optional user", async () => {
    const { client, request } = createHttpClientWithSpies();
    const data = new DATAClient(client);

    await data.getApplicationParameters();
    expect(request).toHaveBeenCalledWith({
      method: "GET",
      path: "/parameters",
      query: undefined,
    });

    await data.getApplicationParameters("user-1");
    expect(request).toHaveBeenCalledWith({
      method: "GET",
      path: "/parameters",
      query: { user: "user-1" },
    });
  });

  it("getMeta includes optional user", async () => {
    const { client, request } = createHttpClientWithSpies();
    const data = new DATAClient(client);

    await data.getMeta("user-1");
    expect(request).toHaveBeenCalledWith({
      method: "GET",
      path: "/meta",
      query: { user: "user-1" },
    });
  });

  it("getInfo and getSite support optional user", async () => {
    const { client, request } = createHttpClientWithSpies();
    const data = new DATAClient(client);

    await data.getInfo();
    await data.getSite("user");

    expect(request).toHaveBeenCalledWith({
      method: "GET",
      path: "/info",
      query: undefined,
    });
    expect(request).toHaveBeenCalledWith({
      method: "GET",
      path: "/site",
      query: { user: "user" },
    });
  });

  it("messageFeedback builds payload from request object", async () => {
    const { client, request } = createHttpClientWithSpies();
    const data = new DATAClient(client);

    await data.messageFeedback({
      messageId: "msg",
      user: "user",
      rating: "like",
      content: "good",
    });

    expect(request).toHaveBeenCalledWith({
      method: "POST",
      path: "/messages/msg/feedbacks",
      data: { user: "user", rating: "like", content: "good" },
    });
  });

  it("fileUpload appends user to form data", async () => {
    const { client, request } = createHttpClientWithSpies();
    const data = new DATAClient(client);
    const form = { append: vi.fn(), getHeaders: () => ({}) };

    await data.fileUpload(form, "user");

    expect(form.append).toHaveBeenCalledWith("user", "user");
    expect(request).toHaveBeenCalledWith({
      method: "POST",
      path: "/files/upload",
      data: form,
    });
  });

  it("filePreview uses bytes response", async () => {
    const { client, request } = createHttpClientWithSpies();
    const data = new DATAClient(client);

    await data.filePreview("file", "user", true);

    expect(request).toHaveBeenCalledWith({
      method: "GET",
      path: "/files/file/preview",
      query: { user: "user", as_attachment: "true" },
      responseType: "bytes",
    });
  });

  it("audioToText appends user and sends form", async () => {
    const { client, request } = createHttpClientWithSpies();
    const data = new DATAClient(client);
    const form = { append: vi.fn(), getHeaders: () => ({}) };

    await data.audioToText(form, "user");

    expect(form.append).toHaveBeenCalledWith("user", "user");
    expect(request).toHaveBeenCalledWith({
      method: "POST",
      path: "/audio-to-text",
      data: form,
    });
  });

  it("textToAudio supports streaming and message id", async () => {
    const { client, request, requestBinaryStream } = createHttpClientWithSpies();
    const data = new DATAClient(client);

    await data.textToAudio({
      user: "user",
      message_id: "msg",
      streaming: true,
    });

    expect(requestBinaryStream).toHaveBeenCalledWith({
      method: "POST",
      path: "/text-to-audio",
      data: {
        user: "user",
        message_id: "msg",
        streaming: true,
      },
    });

    await data.textToAudio("hello", "user", false, "voice");
    expect(request).toHaveBeenCalledWith({
      method: "POST",
      path: "/text-to-audio",
      data: {
        text: "hello",
        user: "user",
        streaming: false,
        voice: "voice",
      },
      responseType: "bytes",
    });
  });

  it("textToAudio requires text or message id", () => {
    const { client } = createHttpClientWithSpies();
    const data = new DATAClient(client);

    expect(() => data.textToAudio({ user: "user" })).toThrow(ValidationError);
  });
});
