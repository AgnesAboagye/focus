<template>
  <header class="header">

    <div class="brand">

      
      <img
        src="/icons/germinate-logo.svg"
        alt="Germinate"
        class="logo"
      />

      <span class="title">Germinate</span>

    </div>

    <div class="header-right">

      <input
        type="text"
        class="search"
        placeholder="Search"
      />

      <!-- Icons -->
      <img src="/icons/help.svg" class="icon" />
      <img src="/icons/theme.svg" class="icon" />
      <img src="/icons/user.svg" class="icon" />
      <img src="/icons/menu.svg" class="icon" />

    </div>

  </header>
</template>

<style scoped>
.header {
  height: 72px;
  background: #f3f4f6;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 25px;
  border-bottom: 1px solid #d1d5db;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.logo {
  height: 50px;
}

.title {
  font-size: 2rem;
  color: #00a3e0;
  font-weight: 300;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 15px;
}

.search {
  width: 300px;
  padding: 10px;
}

.icon {
  width: 20px;
  height: 20px;
  cursor: pointer;
}
</style>