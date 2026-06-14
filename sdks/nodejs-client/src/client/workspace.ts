import { DATAClient } from "./base";
import type { WorkspaceModelType, WorkspaceModelsResponse } from "../types/workspace";
import type { DATAResponse } from "../types/common";
import { ensureNonEmptyString } from "./validation";

export class WorkspaceClient extends DATAClient {
  async getModelsByType(
    modelType: WorkspaceModelType
  ): Promise<DATAResponse<WorkspaceModelsResponse>> {
    ensureNonEmptyString(modelType, "modelType");
    return this.http.request({
      method: "GET",
      path: `/workspaces/current/models/model-types/${modelType}`,
    });
  }
}
