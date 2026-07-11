# The NVIDIA device plugin DaemonSet. A GPU node is not schedulable until this
# plugin advertises `nvidia.com/gpu` as an allocatable resource (Section 4.3).
# Applied with the Kubernetes provider against the cluster the node group joins.
# Shown here so the "provision both the node group and the device plugin" point
# in the chapter is backed by real configuration. The kubernetes provider is
# declared once in versions.tf.

resource "kubernetes_daemon_set_v1" "nvidia_device_plugin" {
  metadata {
    name      = "nvidia-device-plugin-daemonset"
    namespace = "kube-system"
  }

  spec {
    selector {
      match_labels = { name = "nvidia-device-plugin-ds" }
    }

    template {
      metadata {
        labels = { name = "nvidia-device-plugin-ds" }
      }

      spec {
        # Keep the DaemonSet off CPU nodes (matches Listing 4-1).
        node_selector = {
          "workload-type" = "gpu"
        }

        # Tolerate the GPU taint so the plugin can run on GPU nodes.
        toleration {
          key      = "nvidia.com/gpu"
          operator = "Exists"
          effect   = "NoSchedule"
        }

        container {
          # Pin the plugin image; track NVIDIA's releases for updates.
          image = "nvcr.io/nvidia/k8s-device-plugin:v0.17.0"
          name  = "nvidia-device-plugin-ctr"

          security_context {
            privileged = true
          }

          volume_mount {
            name       = "device-plugin"
            mount_path = "/var/lib/kubelet/device-plugins"
          }
        }

        volume {
          name = "device-plugin"
          host_path {
            path = "/var/lib/kubelet/device-plugins"
          }
        }
      }
    }
  }
}
