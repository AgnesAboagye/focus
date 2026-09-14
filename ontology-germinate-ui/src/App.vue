<template>
  <HeaderBar />

  <div class="app-layout">
    <Sidebar />

    <main class="content">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import HeaderBar from "./components/HeaderBar.vue";
import Sidebar from "./components/Sidebar.vue";
</script>

<style>
.app-layout {
  display: flex;
}

.content {
  flex: 1;
  padding: 24px;
  background-color: #f5f5f5;
  min-height: calc(100vh - 72px);
}
</style>