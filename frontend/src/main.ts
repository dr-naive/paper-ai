import { createApp, type Component } from 'vue'
import {
  Avatar,
  Button,
  ConfigProvider,
  Doption,
  Dropdown,
  Drawer,
  Form,
  FormItem,
  Input,
  InputPassword,
  Modal,
  Option,
  Radio,
  RadioGroup,
  Result,
  Select,
  Spin,
  Switch,
  TabPane,
  Tabs,
  Tag,
  Textarea,
  Tooltip,
  Upload
} from '@arco-design/web-vue'
import '@arco-design/web-vue/es/avatar/style/css.js'
import '@arco-design/web-vue/es/button/style/css.js'
import '@arco-design/web-vue/es/dropdown/style/css.js'
import '@arco-design/web-vue/es/drawer/style/css.js'
import '@arco-design/web-vue/es/form/style/css.js'
import '@arco-design/web-vue/es/input/style/css.js'
import '@arco-design/web-vue/es/modal/style/css.js'
import '@arco-design/web-vue/es/radio/style/css.js'
import '@arco-design/web-vue/es/result/style/css.js'
import '@arco-design/web-vue/es/select/style/css.js'
import '@arco-design/web-vue/es/spin/style/css.js'
import '@arco-design/web-vue/es/switch/style/css.js'
import '@arco-design/web-vue/es/tabs/style/css.js'
import '@arco-design/web-vue/es/tag/style/css.js'
import '@arco-design/web-vue/es/textarea/style/css.js'
import '@arco-design/web-vue/es/tooltip/style/css.js'
import '@arco-design/web-vue/es/upload/style/css.js'
import router from './router'
import App from './App.vue'
import { pinia } from './stores'

const app = createApp(App)
const arcoComponents: Array<[string, Component]> = [
  ['AAvatar', Avatar],
  ['AButton', Button],
  ['AConfigProvider', ConfigProvider],
  ['ADoption', Doption],
  ['ADropdown', Dropdown],
  ['ADrawer', Drawer],
  ['AForm', Form],
  ['AFormItem', FormItem],
  ['AInput', Input],
  ['AInputPassword', InputPassword],
  ['AModal', Modal],
  ['AOption', Option],
  ['ARadio', Radio],
  ['ARadioGroup', RadioGroup],
  ['AResult', Result],
  ['ASelect', Select],
  ['ASpin', Spin],
  ['ASwitch', Switch],
  ['ATabPane', TabPane],
  ['ATabs', Tabs],
  ['ATag', Tag],
  ['ATextarea', Textarea],
  ['ATooltip', Tooltip],
  ['AUpload', Upload]
]

app.use(pinia).use(router)
arcoComponents.forEach(([name, component]) => app.component(name, component))
app.mount('#app')
