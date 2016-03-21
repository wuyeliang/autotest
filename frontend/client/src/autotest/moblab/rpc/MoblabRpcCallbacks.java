package autotest.moblab.rpc;

/**
 * Moblab RPC callback interfaces.
 */
public class MoblabRpcCallbacks {
  private MoblabRpcCallbacks() {}

  /**
   * Callback for network info fetch.
   */
  public interface FetchNetworkInfoRpcCallback {
    public void onNetworkInfoFetched(NetworkInfo info);
  }

  /**
   * Callback for cloud storage info fetch.
   */
  public interface FetchCloudStorageInfoCallback {
    public void onCloudStorageInfoFetched(CloudStorageInfo info);
  }

  /**
   * Callback for cloud storage info validation.
   */
  public interface ValidateCloudStorageInfoCallback {
    public void onCloudStorageInfoValidated(OperationStatus status);
  }

  /**
   * Callback for wizard configuration info submission.
   */
  public interface SubmitWizardConfigInfoCallback {
    public void onWizardConfigInfoSubmitted(OperationStatus status);
  }
}
